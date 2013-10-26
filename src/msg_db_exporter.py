#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Daniel Zhang (張道博)'
__copyright__ = 'Copyright (c) 2013, University of Hawaii Smart Energy Project'
__license__ = 'https://raw.github' \
              '.com/Hawaii-Smart-Energy-Project/Maui-Smart-Grid/master/BSD' \
              '-LICENSE.txt'

from msg_logger import MSGLogger
from msg_time_util import MSGTimeUtil
import subprocess
from msg_configer import MSGConfiger
import gzip
import os
import httplib2
import pprint
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client.client import OAuth2WebServerFlow
import argparse
from oauth2client.file import Storage
from apiclient import errors

commandLineArgs = None


def processCommandLineArguments():
    """
    Generate command-line arguments. Load them into global variable
    commandLineArgs.
    """

    global parser, commandLineArgs
    parser = argparse.ArgumentParser(description = '')
    parser.add_argument('--dbname', help = 'Database file to be uploaded.')
    parser.add_argument('--fullpath',
                        help = 'Full path to database file to be uploaded.')
    commandLineArgs = parser.parse_args()


class MSGDBExporter(object):
    """
    Export MSG DBs as SQL scripts.

    Supports export to local storage and to cloud storage.
    """

    def __init__(self):
        """
        Constructor.
        """

        self.logger = MSGLogger(__name__)
        self.timeUtil = MSGTimeUtil()
        self.configer = MSGConfiger()

        # Google Drive parameters.
        self.clientID = self.configer.configOptionValue('Export',
                                                        'google_drive_client_id')
        self.clientSecret = self.configer.configOptionValue('Export',
                                                            'google_drive_client_secret')
        self.oauthScope = 'https://www.googleapis.com/auth/drive'
        self.oauthConsent = 'urn:ietf:wg:oauth:2.0:oob'
        self.googleAPICredentials = ''


    def exportDB(self, databases = None, toCloud = False):
        """
        Export a set of DBs to local storage.

        Uses

        pg_dump -s -h ${HOST} ${DB_NAME} > ${DUMP_TIMESTAMP}_{DB_NAME}.sql

        :param databases: List of database names.
        :param toCloud: If set to True, then export will also be copied to
        cloud storage.
        """

        host = self.configer.configOptionValue('Database', 'db_host')

        for db in databases:
            self.logger.log('Exporting %s.' % db)
            conciseNow = self.timeUtil.conciseNow()
            dumpName = "%s_%s" % (conciseNow, db)
            command = """pg_dump -h %s %s > %s/%s.sql""" % (host, db,
                                                            self.configer
                                                            .configOptionValue(
                                                                'Export',
                                                                'db_export_path'),
                                                            dumpName)
            fullPath = '%s/%s' % (
                self.configer.configOptionValue('Export', 'db_export_path'),
                dumpName)

            try:
                subprocess.check_call(command, shell = True)
            except subprocess.CalledProcessError, e:
                self.logger.log("An exception occurred: %s", e)

            print "Compressing %s using gzip." % db
            self.gzipCompressFile(fullPath)

            if toCloud:
                self.uploadDBToCloudStorage('%s.sql.gz' % fullPath)

            # Remove the uncompressed file.
            try:
                os.remove('%s.sql' % fullPath)
            except OSError, e:
                self.logger.log(
                    'Exception while removing %s.sql: %s.' % (fullPath, e))


    def uploadDBToCloudStorage(self, fullPath = ''):
        """
        Export a DB to cloud storage.

        :param fullPath
        """

        success = True
        dbName = os.path.basename(fullPath)

        storage = Storage('google_api_credentials')
        self.googleAPICredentials = storage.get()

        #print "Retrieving credentials."
        #self.retrieveCredentials()
        #storage.put(self.googleAPICredentials)

        self.logger.log("Authorizing credentials.")
        http = httplib2.Http()
        http = self.googleAPICredentials.authorize(http)

        self.logger.log("Authorized.")

        self.logger.log("Uploading %s." % dbName)

        drive_service = build('drive', 'v2', http = http)

        try:

            media_body = MediaFileUpload(fullPath,
                                         mimetype =
                                         'application/gzip-compressed',
                                         resumable = True)
            body = {'title': dbName,
                    'description': 'Hawaii Smart Energy Project gzip '
                                   'compressed DB export.',
                    'mimeType': 'application/gzip-compressed'}

            file = drive_service.files().insert(body = body,
                                                media_body = media_body)\
                .execute()

            pprint.pprint(file)
        except (errors.ResumableUploadError):
            self.logger.log("Cannot initiate upload of %s." % dbName, 'error')
            success = False

        if success:
            self.logger.log("Finished.")


    def retrieveCredentials(self):
        """
        Perform authorization at the server.
        """

        flow = OAuth2WebServerFlow(self.clientID, self.clientSecret,
                                   self.oauthScope, self.oauthConsent)
        authorize_url = flow.step1_get_authorize_url()
        print 'Go to the following link in your browser: ' + authorize_url
        code = raw_input('Enter verification code: ').strip()
        self.googleAPICredentials = flow.step2_exchange(code)

        print "refresh_token = %s" % self.googleAPICredentials.refresh_token
        print "expiry = %s" % self.googleAPICredentials.token_expiry


    def gzipCompressFile(self, fullPath):
        """
        @todo Test valid compression.
        @todo Move to file utils.

        :param fullPath: Full path of the file to be compressed.
        """

        f_in = open('%s.sql' % fullPath, 'rb')
        f_out = gzip.open('%s.sql.gz' % fullPath, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()


if __name__ == '__main__':
    processCommandLineArguments()
    exporter = MSGDBExporter()

    #exporter.exportDB(
    #    [exporter.configer.configOptionValue('Export', 'dbs_to_export')],
    #    toCloud = True)

    exporter.uploadDBToCloudStorage(commandLineArgs.fullpath)
