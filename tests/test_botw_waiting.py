from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import botw_bridge


class MissingController:
    def __init__(self):self.dev=None;self.closed=False
    def open(self,serial):raise RuntimeError('No controller connected')
    def effect(self,*args):raise AssertionError('Must never send through a null HID handle')
    def close(self):self.closed=True


class Memory:
    def close(self):pass


class State:
    def __init__(self,memory):pass
    def sample(self):return dict(valid=False,effect=False,reason='game-not-running')


class WaitingTests(unittest.TestCase):
    def test_missing_controller_waits_and_exits_without_null_handle_write(self):
        hid=MissingController()
        with patch.object(botw_bridge,'HID',return_value=hid), \
             patch.object(botw_bridge,'LocalMemory',return_value=Memory()), \
             patch.object(botw_bridge,'BotwState',State), \
             patch.object(sys,'argv',['botw_bridge','--pid','123','--seconds','0.04']), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(botw_bridge.main(),0)
        self.assertTrue(hid.closed)


if __name__=='__main__':unittest.main()
