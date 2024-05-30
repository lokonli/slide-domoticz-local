import timerqueue
import threading
import time

queue = timerqueue.TimerQueue()

def producer():
    queue.put('c1')
    queue.put('d5',5)
    queue.put('c2')
    queue.put('d2',2)
    time.sleep(10)
    queue.put('hallo')
    queue.put(None)

def consumer():
    while True:
        res=queue.get()
        print(res)
        time.sleep(1)
        if res==None:
            break

t1 = threading.Thread(target=producer)
t2= threading.Thread(target=consumer)

t1.start()
t2.start()
