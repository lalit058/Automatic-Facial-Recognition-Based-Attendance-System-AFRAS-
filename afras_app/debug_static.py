import traceback
from django.contrib.staticfiles.management.commands.collectstatic import Command

c = Command()
c.set_options(interactive=False, verbosity=3, ignore_patterns=[], dry_run=False, clear=False, link=False, post_process=True, use_default_ignore_patterns=True)
try:
    result = c.collect()
    print('MODIFIED:', len(result.get('modified', [])))
    print('UNMODIFIED:', len(result.get('unmodified', [])))
    print('POST_PROCESSED:', len(result.get('post_processed', [])))
except Exception as e:
    print('EXCEPTION CAUGHT:', repr(e))
    traceback.print_exc()