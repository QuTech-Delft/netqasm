def custom_send(socket):
    socket.send("message from mod.myfunc()")


def custom_recv(socket):
    socket.recv()


def custom_measure(q):
    return q.measure()
