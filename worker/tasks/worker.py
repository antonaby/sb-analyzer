from celery.signals import worker_process_init, worker_shutting_down


@worker_process_init.connect
def init_worker_process(**kwargs):
  from worker.tasks.deps import loop, async_db
  from db.conf import test_db_conn_with_session

  loop.run_until_complete(test_db_conn_with_session(async_db))


@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  from worker.tasks.deps import loop

  loop.run_until_complete(loop.shutdown_asyncgens())
  loop.close()
