"""Options/setup tests and Jianying adapter contract tests (no real app/library)."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import tenniscut as core
import session
import jianying

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.profile_dir = tempfile.TemporaryDirectory()
        self.preference = Path(self.profile_dir.name) / 'preferences.json'
        self.env = patch.dict(os.environ, {'TENNISCUT_PREFERENCES': str(self.preference)})
        self.env.start()
    def tearDown(self):
        self.env.stop();self.profile_dir.cleanup()
    def configure(self, root, threshold=8, draft='no', asking='yes', **extra):
        args=argparse.Namespace(project=root,threshold=threshold,jianying=draft,ask_every_time=asking,**extra)
        return session.configure(args)
    def inspect(self, root, **extra):
        with patch.object(core,'tool',return_value='/existing/tool'):
            return session.inspect(root,**extra)
    def test_fresh_session_has_two_questions_and_requested_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            result=self.inspect(td)
            self.assertEqual([q['key'] for q in result['questions']],
                ['minimum_contacts','generate_jianying_draft'])
            self.assertEqual([q['default'] for q in result['questions']],[8,False])
            self.assertEqual([o['value'] for o in result['questions'][0]['options']],[6,8,10,'custom'])
            self.assertFalse(result['installation_performed'])
            self.assertFalse(self.preference.exists())
            self.assertFalse((Path(td)/'settings.json').exists())
    def test_asking_yes_reopens_two_questions_on_next_invocation(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=10)
            self.assertEqual(len(self.inspect(td)['questions']),2)
            self.assertEqual(len(self.inspect(Path(td)/'another-task')['questions']),2)
            self.assertEqual(self.inspect(td)['questions'][0]['default'],10)
    def test_legacy_asking_no_still_asks_two_choices_in_a_new_project(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(Path(td)/'one',threshold=6,asking='no')
            other=Path(td)/'two'
            result=self.inspect(other)
            self.assertEqual(len(result['questions']),2)
            self.assertEqual(result['settings']['minimum_contacts'],6)
            self.assertFalse(result['settings']['generate_jianying_draft'])
            self.assertEqual(session.resolve_threshold(other),6)
            self.assertFalse(result['project_snapshot_required'])
            self.configure(other,threshold=None,draft=None,asking=None,use_defaults=True)
            self.assertEqual(session.project_choices(other)['minimum_contacts'],6)
    def test_resume_never_reasks_completed_intake(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td)
            self.assertEqual(self.inspect(td,resume=True)['questions'],[])
            self.assertEqual(len(self.inspect(td)['questions']),2)
    def test_custom_count_is_valid_and_explicit_override_takes_priority(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=9,asking='no')
            self.assertEqual(session.resolve_threshold(td),9)
            self.assertEqual(session.resolve_threshold(td,10),10)
            self.assertEqual(self.inspect(td)['settings']['minimum_contacts'],9)
    def test_restore_asking_yes_affects_new_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,asking='no')
            self.assertEqual(len(self.inspect(Path(td)/'next')['questions']),2)
            self.configure(td,threshold=None,draft=None,asking='yes')
            self.assertEqual(len(self.inspect(Path(td)/'next')['questions']),2)
    def test_one_off_override_preserves_reusable_preferences(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,asking='no')
            self.configure(td,threshold=10,draft=None,asking=None,project_only=True,resume=True)
            self.assertEqual(session.resolve_threshold(td),10)
            self.assertEqual(self.inspect(Path(td)/'new-task')['settings']['minimum_contacts'],8)
    def test_explicit_request_fields_are_not_asked_again(self):
        with tempfile.TemporaryDirectory() as td:
            result=self.inspect(td,overrides={'minimum_contacts':9,'generate_jianying_draft':False})
            self.assertEqual([q['key'] for q in result['questions']],[])
            self.assertEqual(result['settings']['minimum_contacts'],9)
            self.assertFalse(self.preference.exists())
    def test_fully_explicit_request_needs_no_duplicate_card(self):
        with tempfile.TemporaryDirectory() as td:
            result=self.inspect(td,overrides={'minimum_contacts':10,'generate_jianying_draft':False,'ask_every_time':False})
            self.assertEqual(result['questions'],[])
            self.assertTrue(result['project_snapshot_required'])
            self.assertFalse(self.preference.exists())
    def test_current_request_wins_when_questions_are_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,asking='no')
            result=self.inspect(Path(td)/'new-task',overrides={'minimum_contacts':10,'generate_jianying_draft':True})
            self.assertEqual(result['settings']['minimum_contacts'],10)
            self.assertTrue(result['settings']['generate_jianying_draft'])
            self.assertEqual(result['questions'],[])
            self.assertEqual(session.read_preferences()['minimum_contacts'],8)
    def test_new_environment_name_wins_and_old_alias_still_works(self):
        with patch.dict(os.environ,{'TENNIS_RALLY_CUT_PREFERENCES':str(self.preference.parent/'old.json')}):
            self.assertEqual(session.preferences_path(),self.preference.resolve())
            os.environ.pop('TENNISCUT_PREFERENCES')
            self.assertEqual(session.preferences_path(),(self.preference.parent/'old.json').resolve())
    def test_renamed_skill_reads_old_preferences_and_writes_new_name(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,{'XDG_CONFIG_HOME':td}), patch.object(session.platform,'system',return_value='Linux'):
            os.environ.pop('TENNISCUT_PREFERENCES',None)
            os.environ.pop('TENNIS_RALLY_CUT_PREFERENCES',None)
            legacy=Path(td)/'tennis-rally-cut/preferences.json'
            core.save(legacy,{'minimum_contacts':10,'generate_jianying_draft':False,'ask_every_time':False})
            before=legacy.read_bytes()
            self.assertEqual(session.read_preferences()['minimum_contacts'],10)
            self.configure(Path(td)/'project',threshold=None,draft=None,asking=None,use_defaults=True)
            self.assertTrue((Path(td)/'tenniscut/preferences.json').exists())
            self.assertEqual(legacy.read_bytes(),before)
    def test_configuration_survives_source_initialization(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td)
            before=(Path(td)/'settings.json').read_bytes()
            with patch.object(core,'source_info',return_value={'id':'v1','path':'synthetic','duration':5}):
                core.init_project(argparse.Namespace(project=td,videos=['synthetic']))
            self.assertEqual((Path(td)/'settings.json').read_bytes(),before)
    def test_unsubmitted_defaults_do_not_authorize_execution_or_persist(self):
        with tempfile.TemporaryDirectory() as td:
            self.inspect(td)
            with self.assertRaises(ValueError):session.resolve_threshold(td)
            self.assertFalse(self.preference.exists())
            self.configure(td,threshold=None,draft=None,asking=None,use_defaults=True)
            self.assertEqual(session.resolve_threshold(td),8)
            self.assertTrue(session.choices(td)['ask_every_time'])
    def test_partial_answer_only_asks_remaining_fields_when_resuming(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=10,draft=None,asking=None)
            self.assertEqual([q['key'] for q in self.inspect(td,resume=True)['questions']],
                             ['generate_jianying_draft'])
            self.assertFalse(self.preference.exists())
    def test_incomplete_no_asking_answer_does_not_suppress_questions(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=None,draft=None,asking='no')
            self.assertEqual(len(self.inspect(td)['questions']),2)
            self.assertFalse(self.preference.exists())
    def test_legacy_two_answer_project_resumes_without_a_third_question(self):
        with tempfile.TemporaryDirectory() as td:
            core.save(Path(td)/'settings.json',{'schema_version':1,'minimum_contacts':7,
                                               'generate_jianying_draft':False})
            self.assertEqual(len(self.inspect(td)['questions']),2)
            self.assertEqual([q['key'] for q in self.inspect(td,resume=True)['questions']],[])
    def test_two_submitted_answers_complete_without_asking_flag(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=10,draft='yes',asking=None)
            self.assertEqual(self.inspect(td,resume=True)['questions'],[])
            self.assertTrue(session.read_preferences()['ask_every_time'])
            self.assertEqual(len(self.inspect(Path(td)/'new')['questions']),2)
    def test_old_false_preference_does_not_suppress_unanswered_field(self):
        with tempfile.TemporaryDirectory() as td:
            core.save(self.preference,{'minimum_contacts':6,'generate_jianying_draft':False,'ask_every_time':False})
            result=self.inspect(td,overrides={'minimum_contacts':10})
            self.assertEqual([q['key'] for q in result['questions']],['generate_jianying_draft'])
            self.assertTrue(result['settings']['ask_every_time'])
    def test_invalid_custom_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for n in [0,-1,True]:
                with self.assertRaises(core.CutError):self.configure(td,threshold=n)
            self.assertFalse(self.preference.exists())
    def test_preference_write_failure_does_not_claim_saved_settings(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(core,'save',side_effect=PermissionError('not writable')):
                with self.assertRaises(core.CutError):self.configure(td,asking='no')
            self.assertFalse((Path(td)/'settings.json').exists())
    def test_intake_only_defers_all_dependency_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(core,'tool',side_effect=AssertionError('No tool discovery before choices')), patch.object(session.importlib.util,'find_spec',side_effect=AssertionError('No package discovery')), patch.object(session.shutil,'which',side_effect=AssertionError('No package manager discovery')):
                result=session.inspect(td,intake_only=True,overrides={'generate_jianying_draft':True})
            self.assertEqual(result['dependency_check'],'deferred')
            self.assertEqual([q['key'] for q in result['questions']],['minimum_contacts'])
            self.assertFalse((Path(td)/'settings.json').exists())
            self.assertFalse(self.preference.exists())
    def test_intake_only_reuses_saved_choices_without_claiming_tools_ready(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,threshold=10,draft='yes',asking='no')
            result=session.inspect(Path(td)/'new',intake_only=True)
            self.assertEqual(len(result['questions']),2)
            self.assertEqual(result['settings']['minimum_contacts'],10)
            self.assertFalse(result['project_snapshot_required'])
            self.assertEqual(result['dependency_check'],'deferred')
            self.assertNotIn('missing_dependencies',result)
    def test_missing_ffmpeg_is_reported_without_installation(self):
        with tempfile.TemporaryDirectory() as td, patch.object(core,'tool',side_effect=core.CutError('missing')):
            result=session.inspect(td)
            self.assertIn('ffmpeg',result['missing_dependencies'])
            self.assertIn('ffprobe',result['missing_dependencies'])
            self.assertFalse(result['installation_performed'])
    def test_jianying_package_checked_only_when_requested(self):
        with tempfile.TemporaryDirectory() as td:
            self.configure(td,draft='no')
            self.assertIsNone(self.inspect(td)['jianying'])
            self.configure(td,draft='yes')
            with patch.object(core,'tool',return_value='/existing/tool'), patch.object(session.importlib.util,'find_spec',side_effect=lambda name: None if name=='pyJianYingDraft' else object()):
                result=session.inspect(td)
            self.assertFalse(result['jianying']['installed'])
            self.assertTrue(any('pyJianYingDraft' in x for x in result['missing_dependencies']))

class FakeLibrary:
    """Contract double based on the documented pyJianYingDraft API, not its implementation."""
    TrackType=types.SimpleNamespace(video='video')
    TrackSpec=staticmethod(lambda kind,name:(kind,name))
    trange=staticmethod(lambda start,duration:{'start':start,'duration':duration})
    VideoMaterial=staticmethod(lambda path:path)
    VideoSegment=staticmethod(lambda material,target_timerange,source_timerange,volume:
        {'target_timerange':target_timerange,'source_timerange':source_timerange,'material':material,'volume':volume})
    class DraftFolder:
        def __init__(self,path):self.path=Path(path)
        def create_draft(self,name,width,height,fps,allow_replace=False):
            p=self.path/name;p.mkdir();core.save(p/'draft_meta_info.json',{})
            return FakeLibrary.Script(p,width,height,fps)
    class Script:
        def __init__(self,path,width,height,fps):
            self.path=path;self.segments=[];self.width=width;self.height=height;self.fps=fps
        def append_track(self,spec):pass
        def add_segment(self,segment,name):self.segments.append(segment)
        def save(self):
            duration=max(s['target_timerange']['start']+s['target_timerange']['duration'] for s in self.segments)
            core.save(self.path/'draft_content.json',{'duration':duration,'canvas_config':{'width':self.width,'height':self.height},
                'fps':self.fps,'tracks':[{'type':'video','segments':self.segments}]})

class JianyingContractTests(unittest.TestCase):
    def test_cli_reports_original_error_without_a_secondary_traceback(self):
        for problem in [core.CutError('No eligible rallies'), PermissionError('Draft folder is not writable')]:
            with self.subTest(problem=str(problem)):
                output=io.StringIO()
                with patch.object(sys,'argv',['jianying.py','missing-project','--draft-root','drafts','--name','test']), patch.object(jianying,'generate',side_effect=problem), contextlib.redirect_stderr(output):
                    code=jianying.main()
                self.assertEqual(code,2)
                self.assertEqual(json.loads(output.getvalue()),{'error':str(problem)})
    def setup_case(self,td):
        root=Path(td);project=root/'project';source=root/'original.mp4';source.write_bytes(b'synthetic stand-in')
        p={'sources':[{'id':'v1','path':str(source),'sha256':core.sha(source),'width':1920,'height':1080}]}
        plan={'duration':5,'rallies':[{'id':'a','source_id':'v1','source_start':12.5,'output_start':0,'output_end':2},
                                    {'id':'b','source_id':'v1','source_start':30,'output_start':2,'output_end':5}]}
        args=argparse.Namespace(project=str(project),threshold=10,fps=30,resolution='source',allow_pending=False,
                               draft_root=str(root/'drafts'),name='tennis')
        return p,plan,args
    def test_new_folder_preserves_separate_source_trims_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            p,plan,args=self.setup_case(td)
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan), patch.object(jianying.importlib,'import_module',return_value=FakeLibrary):
                result=jianying.generate(args)
            draft=Path(result['draft_folder']);content=core.load(draft/'draft_content.json')
            self.assertEqual(content['canvas_config'], {'width':1920,'height':1080})
            segs=content['tracks'][0]['segments']
            self.assertEqual([x['source_timerange']['start'] for x in segs],[12500000,30000000])
            self.assertEqual([x['target_timerange']['start'] for x in segs],[0,2000000])
            self.assertFalse(result['app_open_verified'])
            self.assertEqual(core.load(draft/'draft_meta_info.json')['draft_fold_path'],str(draft))
            self.assertFalse(any(x.name.startswith('tenniscut-draft-') for x in draft.parent.iterdir()))
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan):
                with self.assertRaises(core.CutError):jianying.generate(args)
    def test_missing_optional_dependency_does_not_leave_a_draft(self):
        with tempfile.TemporaryDirectory() as td:
            p,plan,args=self.setup_case(td)
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan), patch.object(jianying.importlib,'import_module',side_effect=ImportError('not installed')):
                with self.assertRaises(core.CutError):jianying.generate(args)
            self.assertFalse((Path(args.draft_root)/args.name).exists())

    def test_explicit_canvas_overrides_source_default(self):
        with tempfile.TemporaryDirectory() as td:
            p,plan,args=self.setup_case(td)
            args.resolution='2560x1440'
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan), patch.object(jianying.importlib,'import_module',return_value=FakeLibrary):
                result=jianying.generate(args)
            content=core.load(Path(result['draft_folder'])/'draft_content.json')
            self.assertEqual(content['canvas_config'], {'width':2560,'height':1440})

    def test_auto_root_generates_separate_clips_without_claiming_app_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            p,plan,args=self.setup_case(td)
            destination=Path(td).resolve()/'app-drafts';destination.mkdir()
            args.draft_root=None
            discovered={'selected_root':str(destination),'attempts':[{'path':str(destination),'directory_verified':True}], 'status':'selected'}
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan), patch.object(jianying.importlib,'import_module',return_value=FakeLibrary), patch.object(jianying.jianying_paths,'discover',return_value=discovered):
                result=jianying.generate(args)
            self.assertEqual(result['delivery_status'],'placed_in_verified_root')
            self.assertFalse(result['app_open_verified'])
            manifest=core.load(Path(result['draft_folder'])/'tenniscut-manifest.json')
            self.assertTrue(manifest['draft_root_verified'])
            self.assertFalse(manifest['app_open_verified'])

    def test_unresolved_auto_root_does_not_create_fallback_or_load_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            p,plan,args=self.setup_case(td);args.draft_root=None
            with patch.object(core,'project',return_value=(Path(args.project),p,[])), patch.object(core,'make_plan',return_value=plan), patch.object(jianying.jianying_paths,'discover',return_value={'selected_root':None,'status':'ambiguous'}), patch.object(jianying.importlib,'import_module') as dependency:
                with self.assertRaisesRegex(core.CutError,'ambiguous'):
                    jianying.generate(args)
                dependency.assert_not_called()
            self.assertFalse((Path(td)/'drafts').exists())

if __name__=='__main__':unittest.main(verbosity=2)
