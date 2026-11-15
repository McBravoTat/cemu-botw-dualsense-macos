#!/bin/zsh
TASK_DIR="${0:A:h}"
if [[ -x /opt/homebrew/bin/python3 ]]; then
  TASK_PYTHON=/opt/homebrew/bin/python3
else
  TASK_PYTHON=python3
fi
"$TASK_PYTHON" "$TASK_DIR/launch_botw.py" "$@"
TASK_RESULT=$?
if (( TASK_RESULT != 0 )) && [[ -t 0 ]]; then
  read -r "?Press Return to close. "
fi
exit $TASK_RESULT
