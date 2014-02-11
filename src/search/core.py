from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.models import signals
from google.appengine.ext import db
try:
    from google.appengine.api.taskqueue import Task
except:
    from google.appengine.api.labs.taskqueue import Task
from ragendja.dbutils import get_filters, get_filtered, generate_key_name, \
    to_json_data, transaction
from ragendja.pyutils import getattr_by_path
from copy import copy, deepcopy
import re
import string
import base64
import cPickle as pickle

_PUNCTUATION_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('-', '').replace(
        '_', '').replace('#', '')) + ']')
_PUNCTUATION_SEARCH_REGEX = re.compile(
    '[' + re.escape(string.punctuation.replace('_', '').replace(
        '#', '')) + ']')

# Various base indexers
def startswith(words, indexing, **kwargs):
    """Allows for word prefix search."""
    if not indexing:
        # In search mode we simply match search terms exactly
        return words
    # In indexing mode we add all prefixes ('h', 'he', ..., 'hello')
    result = []
    for word in words:
        result.extend([word[:count].strip(u'-')
                       for count in range(1, len(word)+1)])
    return result

def porter_stemmer(words, language, **kwargs):
    """Porter-stemmer in various languages."""
    languages = [language,]
    if '-' in language:
        languages.append(language.split('-')[0])

    # Fall back to English
    languages.append('en')

    # Find a stemmer for this language
    for language in languages:
        try:
            stem = __import__('search.porter_stemmers.%s' % language,
                                 {}, {}, ['']).stem
        except:
            continue
        break

    result = []
    for word in words:
        result.append(stem(word))
    return result

stop_words = {
    'en': set(('a', 'an', 'and', 'or', 'the', 'these', 'those', 'whose', 'to')),
    'de': set(('ein', 'eine', 'eines', 'einer', 'einem', 'einen', 'den',
               'der', 'die', 'das', 'dieser', 'dieses', 'diese', 'diesen',
               'deren', 'und', 'oder'))
}

def get_stop_words(language):
    if language not in stop_words and '-' in language:
        language = language.split('-', 1)[0]
    return stop_words.get(language, set())

def non_stop(words, indexing, language, **kwargs):
    """Removes stop words from search query."""
    if indexing:
        return words
    return list(set(words) - get_stop_words(language))

def porter_stemmer_non_stop(words, **kwargs):
    """Combines porter_stemmer with non_stop."""
    return porter_stemmer(non_stop(words, **kwargs), **kwargs)

# Language handler
def site_language(instance, **kwargs):
    """The default language handler tries to determine the language from
    properties in the model instance."""

    # Check if there's a language attribute
    if hasattr(instance, 'language'):
        return instance.language
    if hasattr(instance, 'lang'):
        return instance.lang

    # Does the entity have a language-specific site?
    if hasattr(instance.__class__, 'site'):
        key = instance.__class__.site.get_value_for_datastore(instance)
        if key.name() and key.name().startswith('lang:'):
            return key.name().split(':', 1)[-1]

    # Fall back to default language
    return settings.LANGUAGE_CODE

def default_splitter(text, indexing=False, **kwargs):
    """
    Returns an array of  keywords, that are included
    in query. All character besides of letters, numbers
    and '_' are split characters. The character '-' is a special 
    case: two words separated by '-' create an additional keyword
    consisting of both words without separation (see example).
    
    Examples:
    - text='word1/word2 word3'
      returns ['word1', 'word2', word3]
    - text='word1/word2-word3'
      returns ['word1', 'word2', 'word3', 'word2word3']
    """
    if not text:
        return []
    if not indexing:
        return _PUNCTUATION_SEARCH_REGEX.sub(u' ', text.lower()).split()
    keywords = []
    for word in set(_PUNCTUATION_REGEX.sub(u' ', text.lower()).split()):
        if not word:
            continue
        if '-' not in word:
            keywords.append(word)
        else:
            keywords.extend(get_word_combinations(word))
    return keywords

def get_word_combinations(word):
    """
    'one-two-three'
    =>
    ['one', 'two', 'three', 'onetwo', 'twothree', 'onetwothree']
    """
    permutations = []
    parts = [part for part in word.split(u'-') if part]
    for count in range(1, len(parts) + 1):
        for index in range(len(parts) - count + 1):
            permutations.append(u''.join(parts[index:index+count]))
    return permutations

class DictEmu(object):
    def __init__(self, data):
        self.data = data
    def __getitem__(self, key):
        return getattr(self.data, key)

class SearchableListProperty(db.StringListProperty):
    """
    This is basically a StringListProperty with search support.
    """
    def filter(self, values, filters=(), chain_sort=(), keys_only=False,
               previous_query = None):
        """Returns a query for the given values (creates '=' filters for this
        property and additionally applies filters.
        
        With 'chain_sort' you can additionally do some kind of "fake"-sorting
        of the results. It simply runs multiple queries and combines them
        into a ChainedQueries instance."""
        if not isinstance(values, (tuple, list)):
            values = (values,)
        if previous_query is not None:
            filtered = previous_query
        else:
            if keys_only:
                filtered = self.model_class.all(keys_only=keys_only)
            else:
                filtered = self.model_class.all()
        for value in set(values):
            filtered = filtered.filter(self.name + ' =', value)
        filtered = get_filtered(filtered, *filters)
        if not chain_sort:
            return filtered
        queries = []
        for filters in chain_sort:
            query = deepcopy(filtered)
            queries.append(get_filtered(query, *filters))
        return ChainedQueries(queries)

    def search(self, query, filters=(), chain_sort=(),
            indexer=None, splitter=None, language=settings.LANGUAGE_CODE,
            keys_only=False, previous_query = None):
        if not splitter:
            splitter = default_splitter
        words = splitter(query, indexing=False, language=language)
        if indexer:
            words = indexer(words, indexing=False, language=language)
        # Optimize query
        words = set(words)
        if len(words) >= 4:
            words -= get_stop_words(language)
        # Don't allow empty queries
        if not words and query:
            # This query will never find anything
            return self.filter((), filters=(self.name + ' =', ' '),
                               chain_sort=chain_sort, keys_only=keys_only,
                               previous_query = previous_query)
        return self.filter(sorted(words), filters=filters, chain_sort=chain_sort,
                           keys_only=keys_only,
                           previous_query = previous_query)

class SearchIndexProperty(SearchableListProperty):
    """
    Simple full-text index for the given properties.

    If "values_index" is True you can retrieve a list of matching values
    for this property (all distinct) by calling search(). The result is
    a list of entities whose "value" attribute contains the actual value.

    If "relation_index" is True the index will be stored in a separate entity.

    With "integrate" you can add properties to your values/relation index,
    so they can be searched, too.

    With "filters" you can specify when a values index should be created.
    """
    default_search_queue = getattr(settings, 'DEFAULT_SEARCH_QUEUE', 'default')

    def __init__(self, properties, indexer=None, splitter=default_splitter,
            values_index=False, relation_index=True, integrate='*', filters=(),
            language=site_language, **kwargs):
        if integrate is None:
            integrate = ()
        if values_index:
            relation_index = False
        if integrate == '*' and not relation_index:
            integrate = ()
        if isinstance(properties, basestring):
            properties = (properties,)
        self.properties = properties
        if isinstance(integrate, basestring):
            integrate = (integrate,)
        self.filters = filters
        self.integrate = integrate
        self.splitter = splitter
        self.indexer = indexer
        self.language = language
        self.values_index = values_index
        self.relation_index = relation_index
        if len(properties) == 0:
            raise ValueError('No properties specified for index!')
        if len(properties) != 1 and values_index:
            raise ValueError("You can't specify multiple properties when "
                             "using values_index!")
        super(SearchIndexProperty, self).__init__(**kwargs)

    def should_index(self, values):
        # Check if filter doesn't match
        if not values:
            return False
        for filter, value in get_filters(*self.filters):
            attr, op = filter.split(' ')
            op = op.lower()
            if (op == '=' and values[attr] != value or
                    op == '!=' and values[attr] == value or
                    op == 'in' and values[attr] not in value or
                    op == '<' and values[attr] >= value or
                    op == '<=' and values[attr] > value or
                    op == '>' and values[attr] <= value or
                    op == '>=' and values[attr] < value):
                return False
            elif op not in ('=', '!=', 'in', '<', '<=', '>=', '>'):
                raise ValueError('Invalid search index filter: %s %s' % (filter, value))
        return True

    @transaction
    def update_relation_index(self, parent_key, delete=False):
        model = self._relation_index_model
        
        # Generate key name (at most 250 chars)
        key_name = u'k' + unicode(parent_key.id_or_name())
        if len(key_name) > 250:
            key_name = key_name[:250]
        
        index = model.get_by_key_name(key_name, parent=parent_key)
        
        if not delete:
            parent = self.model_class.get(parent_key)
            values = None
            if parent:
                values = self.get_index_values(parent)
        
        # Remove index if it's not needed, anymore
        if delete or not self.should_index(values):
            if index:
                index.delete()
            return
        
        # Update/create index
        if not index:
            index = model(key_name=key_name, parent=parent_key, **values)

        # This guarantees that we also set virtual @properties
        for key, value in values.items():
            setattr(index, key, value)

        index.put()

    def create_index_model(self):
        attrs = dict(MODEL_NAME=self.model_class._meta.object_name,
                     PROPERTY_NAME=self.name)
        if self.values_index:
            attrs[self.properties[0]] = db.StringProperty(required=True)

        # By default we integrate everything when using relation index
        if self.relation_index and self.integrate == ('*',):
            self.integrate = tuple(property.name
                                   for property in self.model_class._meta.fields
                                   if not isinstance(property, SearchIndexProperty))

        for property_name in self.integrate:
            property = getattr(self.model_class, property_name)
            property = copy(property)
            attrs[property_name] = property
            if hasattr(property, 'collection_name'):
                attrs[property_name].collection_name = '_sidx_%s_%s_%s_set_' % (
                    self.model_class._meta.object_name.lower(),
                    self.name,
                    property_name,
                )
        if self.values_index:
            index_name = 'index_0'
        else:
            index_name = self.name
        attrs[index_name] = SearchIndexProperty(self.properties,
            splitter=self.splitter, indexer=self.indexer,
            language=self.language, relation_index=False)
        if self.values_index:
            self._values_index_model = type(
                'IndexFor__%s__%s' % (self.model_class._meta.object_name,
                                      self.name),
                (db.Model,), attrs)
        elif self.relation_index:
            owner = self
            def __init__(self, parent, *args, **kwargs):
                # Save some space: don't copy the whole indexed text into the
                # relation index property unless the property gets integrated.
                for key, value in kwargs.items():
                    if key in self.properties() or \
                            key not in owner.model_class.properties():
                        continue
                    setattr(self, key, value)
                    del kwargs[key]
                db.Model.__init__(self, parent=parent, *args, **kwargs)
            attrs['__init__'] = __init__
            self._relation_index_model = type(
                'RelationIndex__%s_%s__%s' % (self.model_class._meta.app_label,
                                           self.model_class._meta.object_name,
                                           self.name),
                (db.Model,), attrs)

    def get_index_values(self, model_instance):
        filters = tuple([f[0].split(' ')[0]
                         for f in get_filters(*self.filters)])
        values = {}
        for property in set(self.properties + self.integrate + filters):
            instance = getattr(model_instance.__class__, property)
            if isinstance(instance, db.ReferenceProperty):
                value = instance.get_value_for_datastore(model_instance)
            else:
                value = getattr(model_instance, property)
            if property == self.properties[0] and \
                    isinstance(value, (list, tuple)):
                value = sorted(value)
            values[property] = value
        return values

    def generate_index_key_names(self, values):
        if self.filters and not self.should_index(values):
            return []

        # Remove unneeded values
        filters = tuple([f[0].split(' ')[0]
                         for f in get_filters(*self.filters)])
        for filter in filters:
            if filter not in (self.properties + self.integrate):
                del values[filter]
        key_names = []
        property_values = values[self.properties[0]]
        if not isinstance(property_values, (list, tuple)):
            property_values = (property_values,)
        for property_value in property_values:
            parts = []
            for property in sorted(values.keys()):
                if property == self.properties[0]:
                    parts.extend((property, unicode(property_value)))
                else:
                    parts.extend((property, unicode(values[property])))
            key_names.append((property_value, generate_key_name(*parts)))
        return key_names

    def update_values_index(self, values=None, old_values=None):
        if values and values == old_values:
            return
        model = self._values_index_model
        if values and values[self.properties[0]]:
            new_key_names = self.generate_index_key_names(values)
        else:
            new_key_names = ()
        if old_values and old_values[self.properties[0]]:
            # We've already been put() (is_saved() was True).
            # First, remove shared keys from new and old keys:
            old_key_names = self.generate_index_key_names(old_values)
            old = set([name for v, name in old_key_names])
            new = set([name for v, name in new_key_names])
            old, new = old - new, new - old
            old_key_names = [k for k in old_key_names if k[1] in old]
            new_key_names = [k for k in new_key_names if k[1] in new]
            indexes = model.get_by_key_name([name for v, name in old_key_names])
            to_delete = []
            for index, (property_value, key_name) in enumerate(old_key_names):
                # Delete unused index entries
                filters = []
                for property, value in old_values.items():
                    if property == self.properties[0]:
                        filters.extend((property + ' =', property_value))
                    else:
                        filters.extend((property + ' =', value))
                if indexes[index] and not getattr(self.model_class,
                        self.name).filter((), filters=filters).get():
                    to_delete.append(indexes[index])
            if to_delete:
                db.delete(to_delete)
        if not values:
            return
        if new_key_names:
            to_add = []
            # Reduce number of put() calls by checking with get() whether
            # index entries already exist
            entries = model.get_by_key_name([name for v, name in new_key_names])
            # Create new index entries
            for index, (property_value, key_name) in enumerate(new_key_names):
                # Skip existing entries
                if entries[index]:
                    continue
                values[self.properties[0]] = property_value
                to_add.append(model(key_name=key_name, **values))
            if to_add:
                db.put(to_add)

    def get_value_for_datastore(self, model_instance):
        if self.filters and not self.should_index(DictEmu(model_instance)) \
                or self.relation_index:
            return []
        
        language = self.language
        if callable(language):
            language = language(model_instance, property=self)
        
        index = []
        for property in self.properties:
            values = getattr_by_path(model_instance, property, None)
            if not values:
                values = ()
            elif not isinstance(values, (list, tuple)):
                values = (values,)
            for value in values:
                index.extend(self.splitter(value, indexing=True, language=language))
        if self.indexer:
            index = self.indexer(index, indexing=True, language=language)
        # Sort index to make debugging easier
        setattr(model_instance, self.name, sorted(set(index)))
        return index

    def make_value_from_datastore(self, value):
        return value

    def search(self, query, filters=(), chain_sort=(),
               language=settings.LANGUAGE_CODE, keys_only=False,
               previous_query = None):
        if self.values_index:
            return self._values_index_model.index_0.search(query, filters,
                chain_sort=chain_sort, language=language, keys_only=keys_only,
                previous_query = previous_query)
        elif self.relation_index:
            if previous_query is not None:
                raise ValueError(
                  'Multiple queries not supported on a relation_index')
            items = getattr(self._relation_index_model, self.name).search(query,
                filters, chain_sort=chain_sort, language=language,
                keys_only=True)
            return RelationIndexQuery(self, items, keys_only=keys_only)
        return super(SearchIndexProperty, self).search(query, filters,
            chain_sort=chain_sort, splitter=self.splitter,
            indexer=self.indexer, language=language, keys_only=keys_only,
            previous_query = previous_query)

# Automatically maintain the values and relation index via signals
def post_init(sender, instance, **kwargs):
    # We have to store the previous value (before a put()), so we
    # can update the index
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexProperty) and property.values_index:
            setattr(instance, '_old_of_' + property.name,
                property.get_index_values(instance))

def pre_save(sender, instance, **kwargs):
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexProperty) and \
                property.values_index and not instance.is_saved():
            # If we haven't been saved our old values don't exist, yet
            setattr(instance, '_old_of_' + property.name, None)

def push_update_values_index(model_descriptor, property_name, old_values,
        new_values):
    Task(url=reverse('search.views.update_values_index'),  method='POST',
        params={
            'property_name': property_name,
            'model_descriptor': base64.b64encode(pickle.dumps(model_descriptor)),
            'old_values': base64.b64encode(pickle.dumps(old_values)),
            'new_values': base64.b64encode(pickle.dumps(new_values)),
        }).add(SearchIndexProperty.default_search_queue)

def push_update_relation_index(model_descriptor, property_name, parent_key,
        delete):
    Task(url=reverse('search.views.update_relation_index'),  method='POST',
        params={
            'property_name': property_name,
            'model_descriptor': base64.b64encode(pickle.dumps(model_descriptor)),
            'parent_key':base64.b64encode(pickle.dumps(parent_key)),
            'delete':base64.b64encode(pickle.dumps(delete)),
        }).add(SearchIndexProperty.default_search_queue)

def post(delete, sender, instance, **kwargs):
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexProperty):
            if property.relation_index:
                if delete:
                    parent_key = instance._rel_idx_key_
                else:
                  parent_key = instance.key()
                push_update_relation_index([sender._meta.app_label,
                    sender._meta.object_name], property.name, parent_key, delete)
            elif property.values_index:
                values = None
                old_values = getattr(instance, '_old_of_' + property.name)
                if not delete:
                    values = property.get_index_values(instance)
                if delete or not values == old_values:
                    push_update_values_index([sender._meta.app_label,
                        sender._meta.object_name], property.name, old_values,
                            values)
                if delete:
                    setattr(instance, '_old_of_' + property.name, None)
                else:
                    setattr(instance, '_old_of_' + property.name,
                        property.get_index_values(instance))

def pre_delete(sender, instance, **kwargs):
    instance._rel_idx_key_ = instance.key()

def post_save_committed(sender, instance, **kwargs):
    # Update indexes after transaction
    post(False, sender, instance, **kwargs)

def post_delete_committed(sender, instance, **kwargs):
    # Update indexes after transaction
    post(True, sender, instance, **kwargs)

def install_index_model(sender, **kwargs):
    needs_values_index = False
    needs_relation_index = False
    for property in sender._meta.fields:
        if isinstance(property, SearchIndexProperty) and (
                property.values_index or property.relation_index):
            property.create_index_model()
            if property.values_index:
                needs_values_index = True
            elif property.relation_index:
                needs_relation_index = True
    if needs_values_index or needs_relation_index:
        signals.post_init.connect(post_init, sender=sender)
        signals.pre_save.connect(pre_save, sender=sender)
        signals.post_save_committed.connect(post_save_committed,
                                            sender=sender)
        signals.post_delete_committed.connect(post_delete_committed,
                                              sender=sender)
    if needs_relation_index:
        signals.pre_delete.connect(pre_delete, sender=sender)
signals.class_prepared.connect(install_index_model)

class QueryIterator(object):
    def __init__(self, query):
        self.query = query

    def __iter__(self):
        return iter(self.query[:301])

    def __len__(self):
        return self.count()
    
    def __getitem__(self, index):
        return self.query[index]
    
    def count(self, max=301):
        return self.query.count(max)

class QueryTraits(object):
    def __iter__(self):
        return iter(self[:301])

    def __len__(self):
        return self.count()

    def get(self):
        result = self[:1]
        if result:
            return result[0]
        return None

    def fetch(self, limit=301):
        return self[:limit]

class RelationIndexQuery(QueryTraits):
    """Combines the results of multiple queries by appending the queries in the
    given order."""
    def __init__(self, property, query, keys_only):
        self.model = property.model_class
        self.property = property
        self.query = query
        self.keys_only = keys_only

    def order(self, *args, **kwargs):
        self.query = self.query.order(*args, **kwargs)

    def filter(self, *args, **kwargs):
        self.query = self.query.filter(*args, **kwargs)

    def __getitem__(self, index):
        keys = [key.parent() for key in self.query[index]]
        if self.keys_only:
            return keys
        return [item for item in self.model.get(keys) if item]

    def count(self, max=301):
        return self.query.count(max)

class ChainedQueries(QueryTraits):
    """Combines the results of multiple queries by appending the queries in the
    given order."""
    def __init__(self, queries):
        assert queries
        self.model = queries[0].model
        self.queries = [QueryIterator(query) for query in queries]

    def __getitem__(self, index):
        original_index = index
        if not isinstance(index, slice):
            index = slice(index, index + 1)
        
        start, stop, step = index.start, index.stop, index.step
        if start is None:
            start = 0
        if stop is None:
            raise ValueError('Open-ended slices are not supported')
        if step is None:
            step = 1
        if start < 0 or stop < 0 or start > stop or step != 1:
            raise ValueError('Only slices with start>=0, stop>=0, '
                             'start<=stop, step==1 are supported!')
        
        # Fetch entities
        pos = 0
        result = []
        for query in self.queries:
            if pos < start:
                # Fast forward to start
                delta = start - pos
                pos += query.count(delta)
                # Have we reached start?
                if pos == start:
                    items = query[delta : stop - pos + delta]
                    result.extend(items)
                    pos += len(items)
                continue
            if pos > stop:
                break
            items = query[:stop - pos]
            result.extend(items)
            pos += len(items)
        
        # Check if we only had to fetch a single item
        if not isinstance(original_index, slice):
            return result[0]
        
        return result

    def count(self, max=301):
        counter = 0
        for query in self.queries:
            if counter >= max:
                break
            counter += query.count(max - counter)
        return counter

def make_paginated_filter(filters=(), order=(), bookmark=None,
                          descending=False, debug=False):
    # Get bookmark (marks last result entry which we can restart from).
    # The bookmark is a dictionary containing the values of the previous
    # page's last item.
    if order and not isinstance(order, (tuple, list)):
        order = (order,)
    
    order = list(order)
    filters = get_filters(*filters)
    inequality = [filter for filter in filters
                  if filter[0].strip().endswith(('!=', '>', '<', '>=', '<='))]
    
    if inequality and not order:
        order.append(inequality[0][0].split(' ')[0])
    
    if '__key__' not in order and '-__key__' not in order:
        order.append(descending and bookmark is not None
                     and '-__key__' or '__key__')
    
    if bookmark is None:
        return [(filters, order)]

    # Assert that all of the properties in the query are also in the bookmark.
    # We check sort order below.
    for filter in inequality:
        if filter[0].split(' ')[0] not in bookmark:
            raise ValueError('Property for filter %r not in bookmark!'
                             % (filter,))
    
    if '__key__' not in bookmark:
        raise ValueError('__key__ not in bookmark!')
    
    # Prepare the original query as a template for the derived queries
    for filter in inequality:
        filters.remove(filter)
    
    for property in order:
        property = property.lstrip('-')
        if property == '__key__':
            continue
        if property not in bookmark:
            raise ValueError('Sort order property %s not in bookmark!'
                             % property)
        filters.append((property + ' =', bookmark[property]))
    
    # order_backup gets used in for loop below
    order_backup = order[:]
    for index, property in enumerate(order[:]):
        if property.lstrip('-') != '__key__':
            if descending:
                if property.startswith('-'):
                    order_backup[index] = property.lstrip('-')
                else:
                    order_backup[index] = '-' + property
            order.remove(property)
    
    # Generate derived queries
    queries = []
    for property in reversed(order_backup):
        property_backup = property
        property = property.lstrip('-')
        
        if property != '__key__':
            filters.remove((property + ' =', bookmark[property]))
            order.insert(0, property_backup)
        
        filters_copy = filters[:]
        order_copy = order[:]
        
        if not property_backup.startswith('-'):
            op = ' >'
        else:
            op = ' <'
        filters_copy.append((property + op, bookmark[property]))
        
        # Add back inequality filter on property
        for filter in inequality:
            if filter[0].split(' ')[0] == property and \
                    filter[0].rstrip(' =') != property + op:
                filters_copy.append(filter)
        
        queries.append((filters_copy, order_copy))
    
    return queries

def _get_paginated_query(model, paginated_filter, keys_only=False):
    queries = []
    for filters, order in paginated_filter:
        if keys_only:
            query = model.all(keys_only=keys_only)
        else:
            query = model.all()
        for filter in filters:
            query = query.filter(*filter)
        for property in order:
            query = query.order(property)
        queries.append(query)
    
    return ChainedQueries(queries)

def make_bookmark(entity, filters, order):
    properties = [filter[0].split(' ')[0] for filter in filters[::2]
                  if filter[0].strip().endswith(('!=', '>', '<', '>=', '<='))]
    properties.extend([property.lstrip('-') for property in order])
    properties = set(properties) - set(('__key__',))
    bookmark = to_json_data(entity, properties)
    bookmark['__key__'] = str(entity.key())
    return bookmark

def paginated_query(model, filters=(), order=(), count=10, bookmark=None,
                    unidirectional=False, keys_only=False):
    """Paginates a query using __key__."""
    
    # Decode bookmark
    if bookmark:
        try:
            modulo = len(bookmark) % 4
            if modulo != 0:
              bookmark += ('=' * (4 - modulo))
    
            bookmark = base64.urlsafe_b64decode(str(bookmark))
            bookmark = pickle.loads(bookmark)
        except Exception, e:
            raise ValueError('Bad bookmark (%r)' % e)
    else:
        bookmark = None
    
    if bookmark and '__key__' in bookmark and \
            isinstance(bookmark['__key__'], basestring):
        bookmark['__key__'] = db.Key(bookmark['__key__'])
    
    # We store the query direction 
    descending = bool(bookmark and bookmark.get('!prev!'))
    paginated = make_paginated_filter(filters=filters, order=order,
                                      bookmark=bookmark,
                                      descending=descending)
    query = _get_paginated_query(model, paginated, keys_only=keys_only)
    items = query[:count+1]
    has_next = len(items) == count + 1
    if has_next:
        del items[-1]
    
    prev, next = None, None
    if has_next:
        # If this is descending (prev) it's set below
        next = make_bookmark(items[-1], filters, order)
    
    if not unidirectional:
        # Query backwards to check if there is a "prev" page
        if bookmark is not None:
            paginated2 = make_paginated_filter(filters=filters, order=order,
                                              bookmark=bookmark,
                                              descending=not descending)
            query2 = _get_paginated_query(model, paginated2, keys_only=keys_only)
            if query2.count(1):
                prev = make_bookmark(items[0], filters, order)
        if descending:
            prev, next = next, prev
    
    if descending:
        items.reverse()
    
    if prev:
        prev['!prev!'] = True
        prev = base64.urlsafe_b64encode(pickle.dumps(prev)
                                        ).replace('=', '')
    if next:
        next = base64.urlsafe_b64encode(pickle.dumps(next)
                                        ).replace('=', '')
    return items, prev, next
