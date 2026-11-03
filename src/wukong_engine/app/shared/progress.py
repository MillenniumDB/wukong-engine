"""Logger for the progress of a run, which is shown at every verbosity level.

Detailed logs go to each module's own logger and are only shown when asked for, while what a user always needs to
follow a run (what each step does, how far it got and what it produced) goes to this logger.
"""

import logging

PROGRESS_LOGGER_NAME = 'wukong_engine.progress'

progress = logging.getLogger(PROGRESS_LOGGER_NAME)
