import pytest


@pytest.fixture
def indata_pipeline_outdata():
    from multipipes import Pipeline, Pipe, Node

    indata = Pipe()
    outdata = Pipe()

    def divide(a, b):
        return a / b

    def inc(n):
        return n + 1

    p = Pipeline([
        Node(divide),
        Node(inc, fraction_of_cores=1),
    ])

    p.setup(indata=indata, outdata=outdata)

    return (indata, p, outdata)


def test_pipeline_propagates_exception(indata_pipeline_outdata):
    indata, pipeline, outdata = indata_pipeline_outdata

    pipeline.start()
    indata.put((4, 0))
    pipeline.stop()
    assert len(pipeline.errors) == 1


def test_pipeline_restarts(indata_pipeline_outdata):
    indata, pipeline, outdata = indata_pipeline_outdata
    pipeline.start()
    indata.put((4, 2))

    processes = [process for node in pipeline.nodes
                 for process in node.processes]

    pipeline.restart()

    # old processes should be gone
    assert all(not process.is_alive() for process in processes)

    # new processes should be all running
    assert all(process.is_alive() for node in pipeline.nodes
               for process in node.processes)


def test_pipeline_restarts_on_error(indata_pipeline_outdata):
    print('\n')
    import time

    indata, pipeline, outdata = indata_pipeline_outdata

    pipeline.restart_on_error = True
    pipeline.start()
    processes = [process for node in pipeline.nodes
                 for process in node.processes]
    indata.put((4, 0))
    time.sleep(1)

    assert len(pipeline.errors) == 1
    assert isinstance(pipeline.errors[0], ZeroDivisionError)

    # old processes should be gone
    assert all(not process.is_alive() for process in processes)

    alive = [(process.pid, process.is_alive()) for node in pipeline.nodes
             for process in node.processes]
    print(alive)

    # new processes should be all running
    assert all(process.is_alive() for node in pipeline.nodes
               for process in node.processes)

    indata.put((4, 2))
    assert outdata.get() == 3


def test_pipeline_restart_when_a_process_is_killed(indata_pipeline_outdata):
    import time

    indata, pipeline, outdata = indata_pipeline_outdata

    pipeline.restart_on_error = True
    pipeline.start()
    processes = [process for node in pipeline.nodes
                 for process in node.processes]
    indata.put((4, 0))
    time.sleep(0.1)

    assert len(pipeline.errors) == 1

    # old processes should be gone
    assert all(not process.is_alive() for process in processes)

    # new processes should be all running
    assert all(process.is_alive() for node in pipeline.nodes
               for process in node.processes)

    indata.put((4, 2))
    assert outdata.get() == 3