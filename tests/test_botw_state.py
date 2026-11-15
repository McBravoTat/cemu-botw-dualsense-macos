from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from botw_state import BotwState, TITLE, PLAYER_INFO, POUCH_MANAGER, PLAYER_VTABLE


class Memory:
    actor, tracker, manager, unit, bow_actor, name = [0x40000000 + i * 0x100000 for i in range(6)]

    def __init__(self):
        self.bytes = {}
        self.status = dict(running=True, title_id=TITLE)
        self.put(0x02D799B0, bytes.fromhex('386307cc4e800020'))
        self.put(0x02D8D0E4, bytes.fromhex('386000024e800020'))
        for addr, value in [(PLAYER_INFO,self.tracker),(POUCH_MANAGER,self.manager),
                            (self.tracker+0x30,self.actor),(self.actor+0xe8,PLAYER_VTABLE),
                            (self.actor+0x540,1),(self.actor+0x1320,60),
                            (self.actor+0x7ec,self.unit),(self.actor+0x7f0,72),
                            (self.unit+0x3c,72),(self.unit+0x40,self.bow_actor),
                            (self.bow_actor+4,self.name),(self.actor+0x83c,0x40000000)]:
            self.u32put(addr,value)
        self.put(self.actor+0x928,b'Bow\0')
        self.put(self.name,b'Weapon_Bow_035\0')

    def info(self):
        return self.status

    def put(self, address, data):
        self.bytes.update({address+i:v for i,v in enumerate(data)})

    def u32put(self, address, value):
        self.put(address, struct.pack('>I',value))

    def read(self, address, size):
        return bytes(self.bytes.get(address+i,0) for i in range(size))

    def u32(self, address):
        return struct.unpack('>I',self.read(address,4))[0]


class StateTests(unittest.TestCase):
    def test_prearms_while_bow_in_hand_between_shots(self):
        self.assertTrue(BotwState(Memory()).sample()['effect'])

    def test_real_observed_sequence_stays_on_during_draw_with_zero_flags(self):
        m=Memory();reader=BotwState(m);result=[]
        for state,flags in [(0,0x40000000),(1,0),(2,0),(3,0),(0,0),(0,0x40000000)]:
            m.u32put(m.actor+0x19b4,state);m.u32put(m.actor+0x83c,flags)
            result.append(reader.sample()['effect'])
        self.assertEqual(result,[True,True,True,False,False,True])

    def test_sword_is_off_even_if_bow_flag_remains_set(self):
        m=Memory();m.put(m.actor+0x928,b'Sword\0');m.u32put(m.actor+0x83c,0x40000088)
        self.assertFalse(BotwState(m).sample()['effect'])

    def test_menu_and_map_equipment_snapshot_force_off(self):
        m=Memory();m.u32put(m.manager+0x3812c,0x44000000)
        self.assertFalse(BotwState(m).sample()['effect'])

    def test_first_sheathed_state_does_not_claim_bow_is_ready(self):
        m=Memory();m.put(m.actor+0x928,b'None\0')
        self.assertFalse(BotwState(m).sample()['effect'])

    def test_bad_game_code_refuses_effect(self):
        m=Memory();m.put(0x02D799B0,b'BAD-CODE')
        self.assertFalse(BotwState(m).sample()['valid'])

    def test_unavailable_player_or_other_title_force_off(self):
        for kind in ['title','running','tracker','vtable']:
            m=Memory()
            if kind=='title':m.status['title_id']='0000000000000000'
            elif kind=='running':m.status['running']=False
            elif kind=='tracker':m.u32put(PLAYER_INFO,0)
            else:m.u32put(m.actor+0xe8,0x10111111)
            self.assertFalse(BotwState(m).sample()['effect'])

    def test_unknown_bow_state_forces_off(self):
        m=Memory();m.u32put(m.actor+0x19b4,9)
        self.assertFalse(BotwState(m).sample()['effect'])

    def test_dead_player_forces_off(self):
        m=Memory();m.u32put(m.actor+0x540,0)
        self.assertFalse(BotwState(m).sample()['effect'])

    def test_reused_equipment_handle_is_not_accepted(self):
        m=Memory();m.u32put(m.unit+0x3c,73)
        self.assertFalse(BotwState(m).sample()['effect'])


if __name__=='__main__':unittest.main()
