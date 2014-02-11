# -*- coding: utf-8 -*-
from google.appengine.api import apiproxy_stub_map
from google.appengine.ext import db
from django.core.urlresolvers import reverse, resolve
from django.http import HttpRequest, QueryDict
from django.test import TestCase
from ragendja.pyutils import equal_lists
from ragendja.testutils import ModelTestCase
from search.core import SearchIndexProperty, startswith, \
    porter_stemmer_non_stop, ChainedQueries, make_paginated_filter, \
    paginated_query
from search.views import show_search_results, live_search_results
import base64

class Ref(db.Model):
    name = db.StringProperty()

class Indexed(db.Model):
    # Test normal and prefix index
    one = db.StringProperty()
    one_index = SearchIndexProperty('one', indexer=startswith)
    two = db.StringProperty()
    one_two_index = SearchIndexProperty(('one', 'two'))
    check = db.BooleanProperty()
    add = db.BooleanProperty()
    ref = db.ReferenceProperty(Ref)

    # Test values index
    value = db.StringProperty()
    value_index = SearchIndexProperty('value', integrate=('one', 'check'))
    values_index = SearchIndexProperty('value', values_index=True,
        integrate='one')
    add_index = SearchIndexProperty('value', values_index=True,
        integrate='ref', filters=('add =', True))

    # Test values index for lists
    values_list = db.StringListProperty()
    values_list_index = SearchIndexProperty('values_list', values_index=True)

def run_tasks():
    stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    tasks = stub.GetTasks('default')
    for task in tasks:
        view, args, kwargs = resolve(task['url'])
        request = HttpRequest()
        request.POST = QueryDict(base64.b64decode(task['body']))
        view(request)
        stub.DeleteTask('default', task['name'])

class TestIndexed(ModelTestCase):
    model = Indexed.values_index._values_index_model

    def setUp(self):
        apiproxy_stub_map.apiproxy.GetStub('taskqueue').FlushQueue('default')
        ref = Ref(name='test')
        ref.put()
        
        for i in range(3):
            Indexed(one=u'OneOne%d' % i).put()

        for i in range(3):
            Indexed(one=u'one%d' % i, two='two%d' % i).put()

        for i in range(3):
            Indexed(one=(None, u'ÜÄÖ-+!#><|', 'blub')[i],
                    check=bool(i%2), add=bool(i%2), ref=ref,
                    value=u'value%d test-word' % i,
                    values_list=['bla%d' % j for j in range(i+1)]).put()
        run_tasks()

    def test_setup(self):
        one = Indexed.one_index.search('oNeone1').get()
        rel_one = Indexed.one_index._relation_index_model.all().ancestor(one).get()
        self.assertEqual(len(rel_one.one_index), len(one.one))
        self.assertTrue('oneone1' in rel_one.one_index)
        self.assertEqual(len(Indexed.one_index.search('oneo')), 3)
        self.assertEqual(len(Indexed.one_index.search('one')), 6)

        self.assertEqual(len(Indexed.one_two_index.search('one2')), 1)
        self.assertEqual(len(Indexed.one_two_index.search('two')), 0)
        self.assertEqual(len(Indexed.one_two_index.search('two1')), 1)

        self.assertEqual(len(Indexed.value_index.search('word')), 3)
        self.assertEqual(len(Indexed.value_index.search('test-word')), 3)
        self.validate_state(
            ('value',),
            ('value0 test-word',),
            ('value1 test-word',),
            ('value2 test-word',),
        )
        values = sorted([item.value for item in
                         Indexed.values_index.search('test-word')])
        self.assertEqual(values, ['value0 test-word', 'value1 test-word',
                                  'value2 test-word'])

        self.assertEqual(len(Indexed.value_index.search('value0',
            filters=('check =', False))), 1)
        self.assertEqual(len(Indexed.value_index.search('value1',
            filters=('check =', True, 'one =', u'ÜÄÖ-+!#><|'))), 1)
        self.assertEqual(len(Indexed.value_index.search('value2',
            filters=('check =', False, 'one =', 'blub'))), 1)

    def test_add_index(self):
        # Only one add_index entry should exist
        self.assertEqual(Indexed.add_index._values_index_model.all().count(), 1)
        self.assertEqual(
            Indexed.add_index._values_index_model.all().get().value,
            'value1 test-word')

    def test_change(self):
        one = Indexed.one_index.search('oNeone1').get()
        one.one = 'oneoneone'
        one.put()
        run_tasks()
        self.assertEqual(
            len(Indexed.one_index.search('oNeoneo').get().one_index), 0)
        self.assertEqual(
            len(Indexed.one_index._relation_index_model.one_index.search('oNeoneo').get().one_index), 9)

        value = Indexed.value_index.search('value0').get()
        value.value = 'value1 test-word'
        value.put()
        value.one = 'shidori'
        value.value = 'value3 rasengan/shidori'
        value.put()
        run_tasks()
        self.assertEqual(len(Indexed.value_index.search('rasengan')), 1)
        self.assertEqual(len(Indexed.value_index.search('value3')), 1)

        self.assertEqual(len(self.model.all()), 3)
        for index in self.model.all():
            if index.value.startswith('value1'):
                self.assertTrue(equal_lists(sorted(index.index_0),
                    ['test', 'testword', 'value1', 'word',]))
            elif index.value.startswith('value2'):
                self.assertTrue(equal_lists(sorted(index.index_0),
                    ['test', 'testword', 'value2', 'word',]))
            elif index.value.startswith('value3'):
                self.assertTrue(equal_lists(sorted(index.index_0),
                    ['rasengan', 'shidori', 'value3',]))
            else:
                self.fail('Unknown index entry: %s' % index.value)
        value = Indexed.value_index.search('value3').get()
        value.delete()
        run_tasks()
        self.validate_state(
            ('value',),
            ('value1 test-word',),
            ('value2 test-word',),
        )

class X(db.Model):
    val = db.StringProperty()
    idx = db.IntegerProperty()
    index = SearchIndexProperty('val', indexer=porter_stemmer_non_stop)

def search_test(request):
    return show_search_results(request, X, 'index', chain_sort=(('idx =', 1),
                                                                ('idx =', 2)),
                               template_name='search/test.html')

def live_search_test(request):
    return live_search_results(request, X, 'index', chain_sort=(('idx =', 1),
                                                                ('idx =', 2)))

class ChainTest(TestCase):
    urls = 'search.urls_test'
    
    def setUp(self):
        self.values = [
            X(key_name='c1', val='bum bam bear', idx=1),
            X(key_name='c2', val='bum bam bear'),
            X(key_name='a1', val='bear and bing', idx=2),
            X(key_name='b1', val='beach sand bear', idx=1),
            X(key_name='b2', val='beach sand bear'),
        ]
        db.put(self.values)
        run_tasks()
    
    def test_chain(self):
        chained = ChainedQueries((
            X.all().filter('val =', 'bum bam bear'),
            X.all().filter('val =', 'bear and bing'),
            X.all().filter('val =', 'beach sand bear'),
        ))
        self.assertEqual(list(chained), self.values)
        self.assertEqual(len(chained), len(self.values))

    def test_search(self):
        url = reverse('search.tests.search_test')
        self.assertEqual(self.client.get(url, {'query': 'bear'}).content,
                         'b1,c1,a1,\n')
    
    def test_live_search(self):
        url = reverse('search.tests.live_search_test')
        self.assertEqual(self.client.get(url, {'query': 'bear'}).content,
                         '['
                         '{"data": {}, "result": "beach sand bear", "value": "beach sand bear"}, '
                         '{"data": {}, "result": "bum bam bear", "value": "bum bam bear"}, '
                         '{"data": {}, "result": "bear and bing", "value": "bear and bing"}'
                         ']')

class PaginationTest(TestCase):
    def test_paginated_filter(self):
        # Model.all()
        filters, order = (), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['__key__'])])
        bookmark = {'__key__': '!key!'}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('__key__ >', '!key!')], ['__key__'])])
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark,
                                               descending=True),
                         [([('__key__ <', '!key!')], ['-__key__'])])
        
        # Model.all().filter('x =', 0)
        filters, order = ('x =', 0), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x =', 0)], ['__key__'])])
        bookmark = {'__key__': '!key!'}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 0), ('__key__ >', '!key!')], ['__key__'])])
        
        # Model.all().filter('x >=', 0)
        filters, order = ('x >=', 0), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x >=', 0)], ['x', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x >', 2)], ['x', '__key__'])])
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark,
                                               descending=True),
                         [([('x =', 2), ('__key__ <', '!key!')], ['-__key__']),
                          ([('x <', 2), ('x >=', 0)], ['-x', '-__key__'])])
        
        # Model.all().filter('x =', 0).filter('y >', 0)
        filters, order = ('x =', 0, 'y >', 0), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x =', 0), ('y >', 0)], ['y', '__key__'])])
        bookmark = {'__key__': '!key!', 'y': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 0), ('y =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x =', 0), ('y >', 2)], ['y', '__key__'])])

        # Model.all().filter('x >', 0).filter('x <', 9)
        filters, order = ('x >', 0, 'x <', 9), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x >', 0), ('x <', 9)], ['x', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x >', 2), ('x <', 9)], ['x', '__key__'])])

        # Model.all().filter('__key__ >', 'A').filter('__key__ <', 'Z')
        filters, order = ('__key__ >', 'A', '__key__ <', 'Z'), ()
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('__key__ >', 'A'), ('__key__ <', 'Z')], ['__key__'])])
        bookmark = {'__key__': '!key!'}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('__key__ >', '!key!'), ('__key__ <', 'Z')], ['__key__'])])

        # Model.all().order('x')
        filters, order = (), ('x',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['x', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x >', 2)], ['x', '__key__'])])

        # Model.all().order('-x')
        filters, order = (), ('-x',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['-x', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x <', 2)], ['-x', '__key__'])])

        # Model.all().order('__key__')
        filters, order = (), ('__key__',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['__key__'])])
        bookmark = {'__key__': '!key!'}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('__key__ >', '!key!')], ['__key__'])])

        # Model.all().order('-__key__')
        filters, order = (), ('-__key__',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['-__key__'])])
        bookmark = {'__key__': '!key!'}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('__key__ <', '!key!')], ['-__key__'])])

        # Model.all().order('x').order('-y')
        filters, order = (), ('x', '-y')
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['x', '-y', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2, 'y': 5}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('y =', 5), ('__key__ >', '!key!')], ['__key__']),
                          ([('x =', 2), ('y <', 5)], ['-y', '__key__']),
                          ([('x >', 2)], ['x', '-y', '__key__'])])
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark,
                                               descending=True),
                         [([('x =', 2), ('y =', 5), ('__key__ <', '!key!')], ['-__key__']),
                          ([('x =', 2), ('y >', 5)], ['y', '-__key__']),
                          ([('x <', 2)], ['-x', 'y', '-__key__'])])

        # Model.all().order('x').order('-__key__')
        filters, order = (), ('x', '-__key__')
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([], ['x', '-__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ <', '!key!')], ['-__key__']),
                          ([('x >', 2)], ['x', '-__key__'])])

        # Model.all().filter('x =', 0).order('-y')
        filters, order = ('x =', 0), ('-y',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x =', 0)], ['-y', '__key__'])])
        bookmark = {'__key__': '!key!', 'y': 5}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 0), ('y =', 5), ('__key__ >', '!key!')], ['__key__']),
                          ([('x =', 0), ('y <', 5)], ['-y', '__key__'])])

        # Model.all().filter('x >', 0).filter('x <', 9).order('-x')
        filters, order = ('x >', 0, 'x <', 9), ('-x',)
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order),
                         [([('x >', 0), ('x <', 9)], ['-x', '__key__'])])
        bookmark = {'__key__': '!key!', 'x': 2}
        self.assertEqual(make_paginated_filter(filters=filters,
                                               order=order,
                                               bookmark=bookmark),
                         [([('x =', 2), ('__key__ >', '!key!')], ['__key__']),
                          ([('x <', 2), ('x >', 0)], ['-x', '__key__'])])
    
    def test_paginated_query(self):
        self.values = [
            X(key_name='c1', val='bum bam bear', idx=1),
            X(key_name='c2', val='bum bam bear'),
            X(key_name='a1', val='bear and bing', idx=2),
            X(key_name='b1', val='beach sand bear', idx=1),
            X(key_name='b2', val='beach sand bear'),
        ]
        db.put(self.values)
        run_tasks()
        items, prev, next = paginated_query(X, count=2)
        self.assertEqual([item.key().name() for item in items],
                         ['a1', 'b1'])
        self.assertEqual(prev, None)
        items, prev, next = paginated_query(X, count=2, bookmark=next)
        self.assertEqual([item.key().name() for item in items],
                         ['b2', 'c1'])
        items, prev, next = paginated_query(X, count=2, bookmark=prev)
        self.assertEqual([item.key().name() for item in items],
                         ['a1', 'b1'])
        
        # Now, test unidirectional
        items, prev, next = paginated_query(X, count=2, bookmark=next,
                                            unidirectional=True)
        self.assertEqual([item.key().name() for item in items],
                         ['b2', 'c1'])
        self.assertEqual(prev, None)
