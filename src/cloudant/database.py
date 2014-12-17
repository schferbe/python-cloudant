#!/usr/bin/env python
"""
_database_

API class representing a cloudant database

"""
import json
import posixpath
import urllib

from .document import CloudantDocument
from .errors import CloudantException


class CloudantDatabase(dict):
    """
    _CloudantDatabase_

    """
    def __init__(self, cloudant, database_name, fetch_limit=100):
        super(CloudantDatabase, self).__init__()
        self._cloudant_account = cloudant
        self._database_host = cloudant._cloudant_url
        self._database_name = database_name
        self._r_session = cloudant._r_session
        self._next_startkey = None
        self._fetch_limit = fetch_limit

    _database_url = property(
            lambda x: posixpath.join(
                x._database_host,
                urllib.quote_plus(x._database_name)
            )
        )


    def exists(self):
        resp = self._r_session.get(self._database_url)
        return resp.status_code == 200

    def metadata(self):
        resp = self._r_session.get(self._database_url)
        resp.raise_for_status()
        return resp.json()

    def doc_count(self):
        return self._metadata().get('doc_count')

    def create_document(self, data, throw_on_exists=False):
        doc = CloudantDocument(self, data.get('_id'))
        doc.update(data)
        doc.create()
        super(CloudantDatabase, self).__setitem__(doc['_id'], doc)
        return doc

    def new_document(self):
        """
        _new_document_

        Creates new, empty document
        """
        doc = CloudantDocument(self, None)
        doc.create()
        super(CloudantDatabase, self).__setitem__(doc['_id'], doc)
        return doc

    def create(self):
        """
        _create_

        Create this database if it doesnt exist
        """
        if self.exists():
            return self

        resp = self._r_session.put(self._database_url)
        if resp.status_code == 201:
            return self

        raise CloudantException(
            u"Unable to create database {0}: Reason:{1}".format(
                self._database_url, resp.text
            ),
            code=resp.status_code
        )

    def delete(self):
        """
        _delete_

        Delete this database

        """
        resp = self._r_session.delete(self._database_url)
        resp.raise_for_status()

    def all_docs(self, **kwargs):
        """

        descending  Return the documents in descending by key order boolean false
        endkey  Stop returning records when the specified key is reached string
        include_docs    Include the full content of the documents in the return boolean false
        inclusive_end   Include rows whose key equals the endkey  boolean true
        key Return only documents that match the specified key  string
        limit   Limit the number of the returned documents to the specified number  numeric
        skip    Skip this number of records before starting to return the results  numeric 0
        startkey

        """
        resp = self._r_session.get(posixpath.join(self._database_url, '_all_docs'), params=dict(kwargs))
        data = resp.json()
        return data

    def keys(self, remote=False):
        """
        _keys_

        """
        if not remote:
            return super(CloudantDatabase, self).keys()
        docs = self.all_docs()
        return [ row['id'] for row in docs.get('rows', []) ]

    def __getitem__(self, key):
        if key in self.keys():
            return super(CloudantDatabase, self).__getitem__(key)
        doc = CloudantDocument(self, key)
        if doc.exists():
            doc.fetch()
            super(CloudantDatabase, self).__setitem__(key, doc)
            return doc
        else:
            raise KeyError(key)

    def __iter__(self, remote=True):
        """
        ___iter___ wrapper around dict.__iter__

        By default, fetch docs from couch, in batches equal to
        self._fetch_limit, yielding results as we get them.

        Otherwise, pass through to built-in __iter__.

        @param boolean remote: Governs default behavior of freshly
            fetching docs from couch (if True), or just digging through
            locally cached docs (if False)

        """
        if not remote:
            super(CloudantDatabase, self).__iter__()
        else:
            next_startkey = 0
            while next_startkey is not None:
                docs = self.all_docs(
                    limit=self._fetch_limit + 1,  # Get one extra doc
                                                  # to use as
                                                  # next_startkey
                    include_docs="true",
                    startkey=json.dumps(next_startkey)
                ).get('rows', [])

                if len(docs) > self._fetch_limit:
                    next_startkey = docs.pop()['id']
                else:
                    # This is the last batch of docs, so we set
                    # ourselves up to break out of the while loop
                    # after this pass.
                    next_startkey = None

                for doc in docs:
                    super(CloudantDatabase, self).__setitem__(
                        doc['id'],
                        doc['doc']
                    )
                    yield doc

            raise StopIteration
