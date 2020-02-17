import zmq
import binascii
from threading import Thread, Event, Condition

from pisa import LOG_PREFIX
from common.logger import Logger
from pisa.conf import FEED_PROTOCOL, FEED_ADDR, FEED_PORT, POLLING_DELTA, BLOCK_WINDOW_SIZE
from pisa.block_processor import BlockProcessor

logger = Logger(actor="ChainMonitor", log_name_prefix=LOG_PREFIX)


class ChainMonitor:
    """
    The :class:`ChainMonitor` is the class in charge of monitoring the blockchain (via ``bitcoind``) to detect new
    blocks on top of the best chain. If a new best block is spotted, the chain monitor will notify the
    :obj:`Watcher <pisa.watcher.Watcher>` and the :obj:`Responder <pisa.responder.Responder>` using ``Queues``.

    The :class:`ChainMonitor` monitors the chain using two methods: ``zmq`` and ``polling``. Blocks are only notified
    once per queue and the notification is triggered by the method that detects the block faster.

    Args:
        watcher_queue (:obj:`Queue`): the queue to be used to send blocks hashes to the ``Watcher``.
        responder_queue (:obj:`Queue`): the queue to be used to send blocks hashes to the ``Responder``.

    Attributes:
        best_tip (:obj:`str`): a block hash representing the current best tip.
        last_tips (:obj:`list`): a list of last chain tips. Used as a sliding window to avoid notifying about old tips.
        terminate (:obj:`bool`): a flag to signal the termination of the :class:`ChainMonitor` (shutdown the tower).
        check_tip (:obj:`Event`): an event that's triggered at fixed time intervals and controls the polling thread.
        lock (:obj:`Condition`): a lock used to protect concurrent access to the queues and ``best_tip`` by the zmq and
            polling threads.
        zmqSubSocket (:obj:`socket`): a socket to connect to ``bitcoind`` via ``zmq``.
        watcher_queue (:obj:`Queue`): a queue to send new best tips to the :obj:`Watcher <pisa.watcher.Watcher>`.
        responder_queue (:obj:`Queue`): a queue to send new best tips to the
            :obj:`Responder <pisa.responder.Responder>`.
    """

    def __init__(self, watcher_queue, responder_queue):
        self.best_tip = None
        self.last_tips = []
        self.terminate = False

        self.check_tip = Event()
        self.lock = Condition()

        self.zmqContext = zmq.Context()
        self.zmqSubSocket = self.zmqContext.socket(zmq.SUB)
        self.zmqSubSocket.setsockopt(zmq.RCVHWM, 0)
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
        self.zmqSubSocket.connect("%s://%s:%s" % (FEED_PROTOCOL, FEED_ADDR, FEED_PORT))

        self.watcher_queue = watcher_queue
        self.responder_queue = responder_queue

    def notify_subscribers(self, block_hash):
        """
        Notifies the subscribers (``Watcher`` and ``Responder``) about a new block. It does so by putting the hash in
        the corresponding queue(s).

        Args:
            block_hash (:obj:`str`): the new block hash to be sent to the subscribers.
            block_hash (:obj:`str`): the new block hash to be sent to the subscribers.
        """

        self.watcher_queue.put(block_hash)
        self.responder_queue.put(block_hash)

    def update_state(self, block_hash, max_block_window_size=BLOCK_WINDOW_SIZE):
        """
        Updates the state of the ``ChainMonitor``. The state is represented as the ``best_tip`` and the list of
        ``last_tips``. ``last_tips`` is bounded to ``max_block_window_size``.

        Args:
            block_hash (:obj:`block_hash`): the new best tip.
            max_block_window_size (:obj:`int`): the maximum length of the ``last_tips`` list.

        Returns:
            (:obj:`bool`): ``True`` is the state was successfully updated, ``False`` otherwise.
        """

        if block_hash != self.best_tip and block_hash not in self.last_tips:
            self.last_tips.append(self.best_tip)
            self.best_tip = block_hash

            if len(self.last_tips) > max_block_window_size:
                self.last_tips.pop(0)

            return True

        else:
            return False

    def monitor_chain_polling(self, polling_delta=POLLING_DELTA):
        """
        Monitors ``bitcoind`` via polling. Once the method is fired, it keeps monitoring as long as ``terminate`` is not
        set. Polling is performed once every ``polling_delta`` seconds. If a new best tip if found, the shared lock is
        acquired, the state is updated and the subscribers are notified, and finally the lock is released.

        Args:
             polling_delta (:obj:`int`): the time delta between polls.
        """

        while not self.terminate:
            self.check_tip.wait(timeout=polling_delta)

            # Terminate could have been set while the thread was blocked in wait
            if not self.terminate:
                current_tip = BlockProcessor.get_best_block_hash()

                self.lock.acquire()
                if self.update_state(current_tip):
                    self.notify_subscribers(current_tip)
                    logger.info("New block received via polling", block_hash=current_tip)
                self.lock.release()

    def monitor_chain_zmq(self):
        """
        Monitors ``bitcoind`` via zmq. Once the method is fired, it keeps monitoring as long as ``terminate`` is not
        set. If a new best tip if found, the shared lock is acquired, the state is updated and the subscribers are
        notified, and finally the lock is released.
        """

        while not self.terminate:
            msg = self.zmqSubSocket.recv_multipart()

            # Terminate could have been set while the thread was blocked in recv
            if not self.terminate:
                topic = msg[0]
                body = msg[1]

                if topic == b"hashblock":
                    block_hash = binascii.hexlify(body).decode("utf-8")

                    self.lock.acquire()
                    if self.update_state(block_hash):
                        self.notify_subscribers(block_hash)
                        logger.info("New block received via zmq", block_hash=block_hash)
                    self.lock.release()

    def monitor_chain(self, polling_delta=POLLING_DELTA):
        """
        Main :class:`ChainMonitor` method. It initializes the ``best_tip`` to the current one (by querying the
        :obj:`BlockProcessor <pisa.block_processor.BlockProcessor>`) and creates two threads, one per each monitoring
        approach (``zmq`` and ``polling``).

        Args:
             polling_delta (:obj:`int`): the time delta between polls by the ``monitor_chain_polling`` thread.
        """

        self.best_tip = BlockProcessor.get_best_block_hash()
        Thread(target=self.monitor_chain_polling, daemon=True, kwargs={"polling_delta": polling_delta}).start()
        Thread(target=self.monitor_chain_zmq, daemon=True).start()