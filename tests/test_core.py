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
            p=base/'card-name.ttf';p.write_bytes(b'local game font')
            with self.assertRaises(ValueError):audit_files([p],base)
            p=base/'menu-assets/top.png';p.parent.mkdir();p.write_bytes(b'local game bubble')
            with self.assertRaises(ValueError):audit_files([p],base)
    def test_source_is_not_a_cache(self):
        with self.assertRaises(ValueError):data_dir(APP)
    def test_camera_update_applies_to_existing_import(self):
        from types import SimpleNamespace
        from manager import PetManager
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model.js';model.write_text('cached model')
            entry={'id':'pet_16_1','petId':16,'sourceSignature':'same','localModel':str(model),'preview':str(root/'preview.png'),'viewHeight':3.6456}
            write_json(root/'library.json',{'cache':str(root),'entries':[entry]})
            write_json(root/'pet-16.json',{'signature':'same','entries':[entry]})
            state=SimpleNamespace(data=root,selected=None,settings=SimpleNamespace(value=lambda key,default:default))
            PetManager.reload_library(state)
            self.assertEqual(state.catalog[0]['viewAngles'],read_json(APP/'camera.json')['pet_16_1']['viewAngles'])
            preview=state.catalog[0]['preview'];self.assertNotEqual(preview,entry['preview'])
            PetManager.reload_library(state);self.assertEqual(state.catalog[0]['preview'],preview)
            self.assertEqual(model.read_text(),'cached model')
    def test_euler_order_and_binding_offsets(self):
        q=unity_euler_quaternion([90,90,0]);expected=[.5,.5,-.5,.5]
        self.assertLess(max(abs(a-b) for a,b in zip(q,expected)),1e-12)
        raw={'m_Name':'fixture','m_MuscleClip':{'m_StartTime':0,'m_StopTime':1,'m_Clip':{'data':{'m_StreamedClip':{'data':[],'curveCount':0},'m_DenseClip':{'m_CurveCount':0},'m_ConstantClip':{'data':[90,90,0,1,2,3]}}}},'m_ClipBindingConstant':{'genericBindings':[{'path':1,'typeID':4,'attribute':4},{'path':1,'typeID':4,'attribute':1}]}}
        clip=sample_clip(raw,{1:0});self.assertEqual(61,len(clip['times']));self.assertEqual(clip['tracks'][1]['values'],[1,2,3]*61)

if __name__=='__main__':unittest.main()
