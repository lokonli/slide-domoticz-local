import queue
import time

class TimerQueue(queue.PriorityQueue):

    def __init__(self):
        super().__init__()
        self.taskQueue = queue.PriorityQueue()
    
    def put(self, cmd, timeOut=0):
        timerValue = time.monotonic() + timeOut
        newTask = (timerValue, cmd)
        super().put(newTask)

    def get(self, block=True):
        timeoutValue = None
        if not self.taskQueue.empty():
            triggerTime = self.taskQueue.queue[0][0]
            if triggerTime<=time.monotonic():
                return self.taskQueue.get()[1]
            timeoutValue = triggerTime - time.monotonic()
        try:
            result = super().get(block=block, timeout = timeoutValue)
            if result[0] > time.monotonic():
                self.taskQueue.put(result)
                return self.get(block)
        except queue.Empty:
            if timeoutValue > 0:
                result = self.taskQueue.get()
        return result[1]

    

        