import sys,tempfile,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import write_json,read_json,data_dir,APP
from importer import stamp,game_root
from animation_sampling import unity_euler_quaternion,sample_clip
from scripts.audit_release import audit_files

class CoreTests(unittest.TestCase):
    def test_cache_changes_with_source(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.unity3d';p.write_bytes(b'first');before=stamp([p]);p.write_bytes(b'new-version')
            self.assertNotEqual(before,stamp([p]))
    def test_atomic_manifest_and_invalid_game(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'nested/catalog.json';write_json(p,{'complete':True});self.assertTrue(read_json(p)['complete'])
            self.assertFalse(p.with_suffix('.json.tmp').exists())
            with self.assertRaises(ValueError):game_root(folder)
    def test_assets_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);p=base/'pet-data.js';p.write_text('window.PET_DATA={};')
            with self.assertRaises(ValueError):audit_files([p],base)
            p=base/'hidden.js';p.write_text('window.PET_SOUNDS={};')
            with self.assertRaises(ValueError):audit_files([p],base)
    def test_source_is_not_a_cache(self):
        with self.assertRaises(ValueError):data_dir(APP)
    def test_euler_order_and_binding_offsets(self):
        q=unity_euler_quaternion([90,90,0]);expected=[.5,.5,-.5,.5]
        self.assertLess(max(abs(a-b) for a,b in zip(q,expected)),1e-12)
        raw={'m_Name':'fixture','m_MuscleClip':{'m_StartTime':0,'m_StopTime':1,'m_Clip':{'data':{'m_StreamedClip':{'data':[],'curveCount':0},'m_DenseClip':{'m_CurveCount':0},'m_ConstantClip':{'data':[90,90,0,1,2,3]}}}},'m_ClipBindingConstant':{'genericBindings':[{'path':1,'typeID':4,'attribute':4},{'path':1,'typeID':4,'attribute':1}]}}
        clip=sample_clip(raw,{1:0});self.assertEqual(61,len(clip['times']));self.assertEqual(clip['tracks'][1]['values'],[1,2,3]*61)

if __name__=='__main__':unittest.main()
