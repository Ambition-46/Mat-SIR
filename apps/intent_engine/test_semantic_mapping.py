"""Offline regression tests: python -m unittest apps.intent_engine.test_semantic_mapping."""
import copy
import importlib
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.conf import settings
if not settings.configured:
    settings.configure(INTENT_MODE='cloud', INTENT_CLOUD_API_KEY='test', INSTALLED_APPS=[])

from .semantic_mapping import SemanticFieldMapper, MappingAPI, FieldMappingError, cosine


class MappingTests(unittest.TestCase):
    def mapper(self, nominations=None, threshold=0.8):
        return SemanticFieldMapper({'a': 'alpha', 'b': 'beta'},
            lambda fs, cat: nominations or [[{'field': 'a', 'score': 1.}] for f in fs],
            lambda texts: [[1., 0.] if not t.startswith('b:') else [0., 1.] for t in texts], threshold)

    def test_independent_branches_run_concurrently(self):
        barrier = threading.Barrier(2)
        def embed(texts):
            if texts[0].startswith('a:'):barrier.wait(timeout=2)
            return [[1., 0.] for _ in texts]
        def nominate(fields, catalog):
            barrier.wait(timeout=2);self.assertEqual(set(catalog), {'a', 'b'})
            return [[{'field': 'a', 'score': 1.}]]
        self.assertEqual(SemanticFieldMapper({'a':'alpha','b':'beta'},nominate,embed).resolve([{'field':'源','description':'描述'}]),['a'])

    def test_disagreement_uses_half_weight_and_llm_nominees_only(self):
        m=self.mapper([[{'field':'b','score':1.},{'field':'a','score':0.4}]],threshold=0.7)
        # vector top=a; LLM top=b; b=.5*.5+.5*1=.75 > a=.7
        self.assertEqual(m.resolve([{'field':'源','description':'描述'}]),['b'])
        m=self.mapper([[{'field':'b','score':1.}]],threshold=0.8)
        with self.assertRaises(FieldMappingError):m.resolve([{'field':'源','description':'描述'}])

    def test_agreement_uses_three_quarters_vector(self):
        m=self.mapper([[{'field':'a','score':0.4}]],threshold=0.84)
        self.assertEqual(m.resolve([{'field':'源','description':'描述'}]),['a'])

    def test_calibrated_weights_are_explicit_and_validated(self):
        m=SemanticFieldMapper({'a':'A'},lambda f,c:[ [{'field':'a','score':.4}] ],
                              lambda texts:[[1.] for _ in texts],threshold=.8,
                              vector_weight_agree=.5,vector_weight_disagree=.5)
        with self.assertRaises(FieldMappingError):m.resolve([{'field':'源','description':'描述'}])
        for value in (-.1,1.1,float('nan'),True):
            with self.subTest(value=value),self.assertRaises(FieldMappingError):
                SemanticFieldMapper({'a':'A'},None,None,vector_weight_agree=value)

    def test_reject_unknown_duplicate_nan_out_of_range_empty(self):
        for cs in [[],[{'field':'unknown','score':1}], [{'field':'a','score':1}]*2,
                   [{'field':'a','score':float('nan')}],[{'field':'a','score':1.1}]]:
            m=self.mapper();m.llm=lambda f,c,cs=cs:[cs]
            with self.subTest(cs=cs), self.assertRaises(FieldMappingError):m.resolve([{'field':'源','description':'描述'}])

    def test_sir_values_logic_projection_sort_and_aggregate_preserved(self):
        sir={'groups':[{'logic_op':'or','conditions':[{'field':'源','field_description':'描述','operator':'>','value':2.1e-8,'unit':'MPa','agg_func':None},{'field':'源','field_description':'描述','operator':None,'value':None,'agg_func':'MAX'}],'datasets':['dataset']}], 'group_logic_op':'not','target_properties':['源'],'sort_by':{'field':'源','order':'desc'}}
        original=copy.deepcopy(sir);mapped=self.mapper().map_sir(sir,'question')
        self.assertEqual(sir,original);self.assertEqual(mapped['groups'][0]['conditions'][0]['value'],2.1e-8)
        self.assertEqual(mapped['groups'][0]['conditions'][1]['agg_func'],'MAX')
        self.assertEqual(mapped['target_properties'],['a']);self.assertEqual(mapped['sort_by'],{'field':'a','order':'desc'})
        self.assertEqual(mapped['group_logic_op'],'not');self.assertEqual(mapped['groups'][0]['logic_op'],'or')

    def test_invalid_vectors(self):
        for a,b in [([0.],[1.]),([1.],[1.,2.]),([float('nan')],[1.])]:
            with self.assertRaises(FieldMappingError):cosine(a,b)

    def test_catalog_embeddings_cached(self):
        m=self.mapper();m.embed=Mock(wraps=m.embed)
        m.resolve([{'field':'源','description':'描述'}]);m.resolve([{'field':'源2','description':'描述'}])
        self.assertEqual(m.embed.call_count,3)

    def test_provider_response_indices_not_positional(self):
        api=MappingAPI(SimpleNamespace(api_base='http://example',api_key='test',model='qwen3-32b',mode='cloud'),SimpleNamespace())
        data={'choices':[{'message':{'content':json.dumps({'matches':[{'index':1,'candidates':[{'id':1,'score':1}]},{'index':0,'candidates':[{'id':0,'score':1}]}]})}}]}
        with patch.object(api,'_post',return_value=data):
            out=api.nominate([{'field':'x'},{'field':'y'}],{'a':'A','b':'B'})
        self.assertEqual(out[0][0]['field'],'a')

    def test_process_cache_is_separated_by_model_and_catalog_text(self):
        MappingAPI._embedding_cache.clear()
        parser=SimpleNamespace(api_base='http://example',api_key='test',model='model',mode='cloud')
        first=MappingAPI(parser,SimpleNamespace())
        response={'data':[{'index':0,'embedding':[1.,0.]}]}
        with patch.object(first,'_post',return_value=response) as request:
            first.embed(['a: original'])
            first.embed(['a: original'])
            self.assertEqual(request.call_count,1)
            first.embed(['a: changed'])
            self.assertEqual(request.call_count,2)
        second=MappingAPI(parser,SimpleNamespace(INTENT_EMBEDDING_MODEL='other'))
        with patch.object(second,'_post',return_value=response) as request:
            second.embed(['a: original']);request.assert_called_once()
        MappingAPI._embedding_cache.clear()

    def test_provider_embedding_validation(self):
        api=MappingAPI(SimpleNamespace(api_base='http://example',api_key='test',model='model',mode='cloud'),SimpleNamespace())
        with patch.object(api,'_post',return_value={'data':[{'index':0,'embedding':[1.]},{'index':0,'embedding':[1.]}]}),self.assertRaises(FieldMappingError):api.embed(['x','y'])

    def test_candidate_ids_are_requested_fresh(self):
        api=MappingAPI(SimpleNamespace(api_base='http://example',api_key='test',model='model',mode='cloud'),SimpleNamespace())
        response={'choices':[{'message':{'content':json.dumps({'matches':[{'index':0,'candidates':[{'id':0,'score':.9}]}]})}}]}
        with patch.object(api,'_post',return_value=response) as request:
            first=api.nominate([{'field':'x','description':'context'}],{'a':'A'})
            first[0][0]['field']='mutated'
            self.assertEqual(api.nominate([{'field':'x','description':'context'}],{'a':'A'})[0][0]['field'],'a')
            self.assertEqual(request.call_count,2)
            api.nominate([{'field':'x','description':'different context'}],{'a':'A'})
            api.nominate([{'field':'x','description':'context'}],{'a':'different catalog'})
            self.assertEqual(request.call_count,4)

    def test_invalid_id_not_cached_or_repaired_by_name(self):
        api=MappingAPI(SimpleNamespace(api_base='http://example',api_key='test',model='model',mode='cloud'),SimpleNamespace())
        for identifier in (-1,1,True,'a'):
            response={'choices':[{'message':{'content':json.dumps({'matches':[{'index':0,'candidates':[{'id':identifier,'score':.9}]}]})}}]}
            with patch.object(api,'_post',return_value=response),self.assertRaises(FieldMappingError):
                api.nominate([{'field':'x'}],{'a':'A'})

    def test_no_schema_repair_or_retry_on_valid_abstention(self):
        api=MappingAPI(SimpleNamespace(api_base='http://example',api_key='test',model='model',mode='cloud'),SimpleNamespace())
        def response(candidates):
            return {'choices':[{'message':{'content':json.dumps({'matches':[{'index':0,'candidates':candidates}]})}}]}
        with patch.object(api,'_post',side_effect=[response([{'id':9,'score':1}]),response([{'id':0,'score':.9}])]) as request:
            with self.assertRaises(FieldMappingError):
                api.nominate([{'field':'x'}],{'a':'A'})
            self.assertEqual(request.call_count,1)
        with patch.object(api,'_post',return_value=response([])) as request:
            self.assertEqual(api.nominate([{'field':'unknown'}],{'a':'A'}),[[]])
            self.assertEqual(request.call_count,1)


class ParserIntegrationTests(unittest.TestCase):
    def test_retrieval_threshold_is_scoped_and_overrides_legacy(self):
        from django.test import override_settings
        for path in ['apps.intent_engine.parser']:
            module=importlib.import_module(path)
            with self.subTest(parser=path), patch.object(module,'_ensure_property_file_fresh'), \
                 patch.object(module,'catalog_from_lines',return_value={'hardness':'硬度'}):
                p=module.IntentParser()
                self.assertEqual(p._refresh_mapper().threshold,.75)
                with override_settings(INTENT_MAPPING_THRESHOLD=.91):
                    p=module.IntentParser()
                    self.assertEqual(p._refresh_mapper().threshold,.91)
                    with override_settings(INTENT_RETRIEVAL_MAPPING_THRESHOLD=.77):
                        p=module.IntentParser()
                        self.assertEqual(p._refresh_mapper().threshold,.77)

    def test_both_parsers_map_and_fail_closed(self):
        for path in ['apps.intent_engine.parser']:
            module=importlib.import_module(path)
            with self.subTest(parser=path),patch.object(module,'_ensure_property_file_fresh'):
                p=module.IntentParser()
                self.assertNotIn('易错点补充',p.system_prompt)
                sir={'groups':[{'conditions':[{'field':'硬度','operator':'>','value':200}]}]}
                mapper=SemanticFieldMapper({'hardness':'硬度'},lambda f,c:[ [{'field':'hardness','score':1}] for _ in f],lambda texts:[[1.] for t in texts])
                with patch.object(p,'_call_llm',return_value=json.dumps(sir)),patch.object(p,'_refresh_mapper',return_value=mapper):
                    out=p.parse('硬度大于200');self.assertEqual(out.groups[0].conditions[0].field,'hardness')
                with patch.object(p,'_call_llm',return_value=json.dumps(sir)),patch.object(p,'_refresh_mapper',side_effect=FieldMappingError('unmatched')),patch.object(p,'_simple_parse') as fallback:
                    self.assertIsNone(p.parse('未知字段'));fallback.assert_not_called()
                with patch.object(p,'_call_llm',return_value=None),patch.object(p,'_simple_parse') as fallback:
                    self.assertIsNone(p.parse('硬度'));fallback.assert_not_called()

    def test_feature_flag_restores_previous_path(self):
        from django.test import override_settings
        module=importlib.import_module('apps.intent_engine.parser')
        with override_settings(INTENT_SEMANTIC_MAPPING_ENABLED=False),patch.object(module,'_ensure_property_file_fresh'):
            p=module.IntentParser()
            with patch.object(p,'_call_llm',return_value=None),patch.object(p,'_simple_parse',return_value='fallback'):
                self.assertEqual(p.parse('test'),'fallback')

if __name__=='__main__':unittest.main()
