#!/usr/bin/python3
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.
#
# Developed by: Nasel(http://www.nasel.com.ar)
#
# Authors:
# Matías Fontanini
# Santiago Alessandri
# Gastón Traberg

from sys import exit

import connection, os
import themole
import traceback, codecs
from base64 import b64encode
from exceptions import *

class Command:
    def check_initialization(self, mole):
        if not mole.initialized:
            try:
                mole.initialize()
            except MoleAttributeRequired as ex:
                raise CommandException('Mole not ready: ' + str(ex), False)
            except PageNotFound as ex:
                raise CommandException('Could not detect SQL Injection: Page not found (' + str(ex) + ')', False)
            except NeedleNotFound as ex:
                raise CommandException('Could not detect SQL Injection: Needle not found (' + str(ex) + ')', False)
            except SeparatorNotFound as ex:
                raise CommandException('Could not exploit SQL Injection: Separator not found (' + str(ex) + ')', False)
            except CommentNotFound as ex:
                raise CommandException('Could not exploit SQL Injection: Comment marker not found (' + str(ex) + ')', False)
            except ColumnNumberNotFound as ex:
                raise CommandException('Could not exploit SQL Injection: Number of columns not found (' + str(ex) + ')', False)
            except InjectableFieldNotFound as ex:
                raise CommandException('Could not exploit SQL Injection: Injectable field not found (' + str(ex) + ')', False)
            except DbmsDetectionFailed as ex:
                raise CommandException('Could not exploit SQL Injection: DBMS detection failed (' + str(ex) + ')', False)
            except EncodingNotFound as ex:
                raise CommandException('Could not exploit SQL Injection: HTML encoding not found (' + str(ex) + ')', False)
            except StoppedQueryException:
                raise QuietCommandException()

    def execute(self, mole, params):
        pass

    def usage(self, cmd_name):
        return cmd_name

    def parameters(self, mole, current_params):
        return []

    def parameter_separator(self, current_params):
        return ' '

    def requires_smart_parse(self):
        return True

class URLCommand(Command):
    def execute(self, mole, params):
        if len(params) < 1:
            if not mole.get_url():
                output_manager.normal('No url defined').line_break()
            else:
                output_manager.normal(mole.get_url()).line_break()
        else:
            url = params[0]
            if len(params) == 2:
                mole.set_url(url, params[1])
            else:
                mole.set_url(url)
            mole.restart()

    def usage(self, cmd_name):
        return cmd_name + ' [URL] [PARAM]'

    def parameters(self, mole, current_params):
        if len(current_params) == 1:
            return list(t.split('=', 1)[0] for t in current_params[0].split('&'))
        else:
            return []

class CookieCommand(Command):
    def execute(self, mole, params):
        if not mole.requester:
            raise CommandException('URL must be set first.')
        if len(params) == 1:
            mole.requester.set_cookie_params(' '.join(params))
        elif len(params) > 1:
            raise CommandException('Too many arguments(remember to use quotes when setting the cookie).')
        else:
            try:
                output_manager.normal(mole.requester.headers['Cookie']).line_break()
            except KeyError:
                output_manager.normal('No cookie set yet.').line_break()

    def usage(self, cmd_name):
        return cmd_name + ' [COOKIE]'

class RedirectCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal('on' if mole.requester.follow_redirects else 'off').line_break()
        else:
            if params[0] == 'on':
                value = True
            elif params[0] == 'off':
                value = False
            else:
                raise CommandException('Expected "on" or "off" as argument')
            mole.requester.follow_redirects = value

    def usage(self, cmd_name):
        return cmd_name + ' [on|off]'

    def parameters(self, mole, current_params):
        return ['on', 'off'] if len(current_params) == 0 else []

class NeedleCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            if not mole.needle:
                output_manager.normal('No needle defined').line_break()
            else:
                output_manager.normal(mole.needle).line_break()
        else:
            mole.needle = ' '.join(params)

    def usage(self, cmd_name):
        return cmd_name + ' [NEEDLE]'

    def parameters(self, mole, current_params):
        return []

class ClearScreenCommand(Command):
    def execute(self, mole, params):
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')

class FetchDataCommand(Command):
    def __init__(self):
        self.cmds = {
                        'schemas' : SchemasCommand(True),
                        'tables'  : TablesCommand(True),
                        'columns' : ColumnsCommand(True),
                    }

    def execute(self, mole, params):
        self.check_initialization(mole)
        if len(params) == 0:
            raise CommandException('At least one parameter is required!')
        self.cmds[params[0]].execute(mole, params[1:], output_manager)

    def usage(self, cmd_name):
        return cmd_name + ' <schemas|tables|columns> [args]'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return ['schemas', 'tables', 'columns']
        else:
            try:
                return self.cmds[current_params[0]].parameters(mole, current_params[1:])
            except KeyError:
                return []


class SchemasCommand(Command):
    def __init__(self, force_fetch=False):
        self.force_fetch = force_fetch

    def execute(self, mole, params):
        self.check_initialization(mole)
        try:
            schemas = mole.get_databases(self.force_fetch)
        except QueryError as ex:
            output_manager.error('Query error: {0}'.format(ex)).line_break()
            return

        parser = output_manager.results_output(['Databases'])
        schemas.sort()
        for i in schemas:
            parser.put([i])
        parser.end_sequence()

    def parameters(self, mole, current_params):
        return []

class TablesCommand(Command):
    def __init__(self, force_fetch=False):
        self.force_fetch = force_fetch

    def execute(self, mole, params):
        if len(params) != 1:
            raise CommandException('Database name required')
        try:
            self.check_initialization(mole)
            tables = mole.get_tables(params[0], self.force_fetch)
        except QueryError as ex:
            output_manager.error('Query error: {0}'.format(ex)).line_break()
            return
        parser = output_manager.results_output(['Tables'])
        tables.sort()
        for i in tables:
            parser.put([i])
        parser.end_sequence()

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA>'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            return schemas if schemas else []
        else:
            return []

class FindTablesLikeCommand(Command):
    def execute(self, mole, params):
        if len(params) != 2:
            raise CommandException('Database and table filter required.')
        try:
            self.check_initialization(mole)
            tables = mole.find_tables_like(params[0], "'" + ' '.join(params[1:]) + "'")
        except QueryError as ex:
            output_manager.error('Query error: {0}'.format(ex)).line_break()
            return
        parser = output_manager.results_output(['Tables'])
        tables.sort()
        for i in tables:
            parser.put([i])
        parser.end_sequence()

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA> <FILTER>'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            return schemas if schemas else []
        else:
            return []

class ColumnsCommand(Command):
    def __init__(self, force_fetch=False):
        self.force_fetch = force_fetch

    def execute(self, mole, params):
        if len(params) != 2:
            raise CommandException('Database name required')
        try:
            self.check_initialization(mole)
            columns = mole.get_columns(params[0], params[1], force_fetch=self.force_fetch)
        except QueryError as ex:
            output_manager.error('Query error: {0}'.format(ex)).line_break()
            return
        columns.sort()
        parser = output_manager.results_output(['Columns for table ' + params[1]])
        for i in columns:
            parser.put([i])
        parser.end_sequence()

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA> <TABLE>'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            if not schemas:
                return []
            return [i for i in schemas if mole.poll_tables(i) != None]
        elif len(current_params) == 1:
            tables = mole.poll_tables(current_params[0])
            return tables if tables else []
        else:
            return []

class QueryCommand(Command):
    def execute(self, mole, params):
        if len(params) < 3:
            raise CommandException('Database name required')
        try:
            self.check_initialization(mole)
            if len(params) == 4:
                raise CommandException('Expected 3 or at least 5 parameters, got 4.')
            index_limit = params.index('limit') if 'limit' in params else -1
            index_where = params.index('where') if 'where' in params else -1
            index_offset = params.index('offset') if 'offset' in params else -1
            min_end = min(index_limit if index_limit != -1 else 0x7fffff, index_offset if index_offset != -1 else 0x7fffff)
            if min_end == 0x7fffff:
                min_end = -1
            where_end = min_end if min_end != -1 and min_end > index_where else len(params) + 1
            condition = ' '.join(params[index_where + 1:where_end]) if index_where != -1 else '1=1'
            if index_limit == len(params) - 1:
                raise CommandException('Limit argument requires row numbers.')
            if index_offset == len(params) - 1:
                raise CommandException('Offset argument requires row index.')
            try:
                limit = int(params[index_limit + 1]) if index_limit != -1 else 0x7fffffff
                limit = max(limit, 0)
                offset = int(params[index_offset + 1]) if index_offset != -1 else 0
                offset = max(offset, 0)
            except ValueError:
                raise CommandException("Non-int value given.")
            if params[2] != '*':
                columns = params[2].strip("'").strip('"').split(',')
            else:
                columns = mole.poll_columns(params[0], params[1])
                if columns is None:
                    raise CommandException("Columns must be dumped first in order to use '*'.", False)
                columns.sort()
            result = mole.get_fields(params[0], params[1], columns, condition, start=offset, limit=limit)
        except themole.QueryError as ex:
            output_manager.error('Query error: {0}'.format(ex)).line_break()
            return
        res_out = output_manager.results_output(columns)
        for i in result:
            res_out.put(i)
        res_out.end_sequence()

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA> <TABLE> <COLUMNS> [where <CONDITION>] [limit <NUM_ROWS>] [offset <OFFSET>]'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            if not schemas:
                return []
            return schemas
        elif len(current_params) == 1:
            tables = mole.poll_tables(current_params[0])
            if not tables:
                return []
            return tables
        elif len(current_params) == 3 :
            return ['where', 'limit', 'offset']
        else:
            columns = mole.poll_columns(current_params[0], current_params[1])
            return columns if columns else []

    def parameter_separator(self, current_params):
        return ' ' if len(current_params) <= 1 else ''

    def requires_smart_parse(self):
        return False

class DBInfoCommand(Command):
    def execute(self, mole, params):
        self.check_initialization(mole)
        try:
            info = mole.get_dbinfo()
        except QueryError:
            output_manager.error('There was an error with the query.').line_break()
            return
        output_manager.advance("User:\t{0}".format(info[0])).line_break()
        output_manager.advance("Version:\t{0}".format(info[1])).line_break()
        output_manager.advance("Database:\t{0}".format(info[2])).line_break()

    def parameters(self, mole, current_params):
        return []

class UserCredentialsCommand(Command):
    def execute(self, mole, params):
        self.check_initialization(mole)
        try:
            result = mole.get_user_creds()
        except QueryError:
            print('[-] There was an error with the query.')
            return
        output_manager.begin_sequence(['User', 'Password'])
        for i in result:
            output_manager.put(i)
        output_manager.end_sequence()

    def parameters(self, mole, current_params):
        return []

class BruteforceTablesCommand(Command):
    def execute(self, mole, params):
        self.check_initialization(mole)
        if len(params) < 2:
            raise CommandException("DB name and table names to bruteforce required.")
        else:
            mole.brute_force_tables(params[0], params[1:])

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA> TABLE1 [TABLE2 [...]]'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            return [] if not schemas else schemas
        return []

class BruteforceUserTableCommand(Command):
    def execute(self, mole, params):
        self.check_initialization(mole)
        if len(params) == 0:
            raise CommandException("DB name expected as argument.")
        else:
            mole.brute_force_users_tables(params[0])

    def usage(self, cmd_name):
        return cmd_name + ' <SCHEMA>'

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            schemas = mole.poll_databases()
            return [] if not schemas else schemas
        return []

class ExitCommand(Command):
    def execute(self, mole, params):
        mole.abort_query()
        mole.threader.stop()
        exit(0)

class QueryModeCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal(mole.mode).line_break()
        else:
            if not params[0] in ['union', 'blind']:
                raise CommandException('Invalid query mode.')
            mole.set_mode(params[0])

    def parameters(self, mole, current_params):
        return ['union', 'blind'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <union|blind>'

class PrefixCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal(mole.prefix).line_break()
        else:
            if params[0].startswith('"') or params[0].startswith('\''):
                mole.prefix = ' '.join(params)
            else:
                mole.prefix = ' ' + ' '.join(params)

    def usage(self, cmd_name):
        return cmd_name + ' [PREFIX]'

class SuffixCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal(mole.suffix).line_break()
        else:
            if params[0].startswith('"') or params[0].startswith('\''):
                mole.suffix = ' '.join(params)
            else:
                mole.suffix = ' ' + ' '.join(params)

    def usage(self, cmd_name):
        return cmd_name + ' [SUFFIX]'

class DelayCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal(mole.delay).line_break()
        else:
            mole.delay = float(params[0])
            if mole.requester:
                mole.requester.delay = mole.delay

    def usage(self, cmd_name):
        return cmd_name + ' [DELAY]'

class VerboseCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal('on' if mole.verbose else 'off').line_break()
        else:
            if not params[0] in ['on', 'off']:
                raise CommandException('Invalid parameter.')
            mole.verbose = True if params[0] == 'on' else False

    def parameters(self, mole, current_params):
        return ['on', 'off'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <on|off>'

class OutputCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            output_manager.normal(output_manager.result_output).line_break()
        else:
            if not params[0] in ['pretty', 'plain']:
                raise CommandException('Invalid parameter.')
            output_manager.result_output = params[0]

    def parameters(self, mole, current_params):
        return ['pretty', 'plain'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <pretty|plain>'

class UsageCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            raise CommandException('Command required as argument')
        else:
            cmd = cmd_manager.find(params[0])
            output_manager.normal(' {0}'.format(cmd.usage(params[0]))).line_break()

    def parameters(self, mole, current_params):
        return cmd_manager.cmds.keys() if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <CMD_NAME>'

class BaseFilterCommand(Command):
    def __init__(self, functor):
        self.functor = functor

    def execute(self, mole, params):
        if len(params) == 0:
            filters = self.functor(mole).active_filters_to_string()
            if len(filters) == 0:
                output_manager.normal('No filters added yet.').line_break()
            else:
                for i in filters:
                    output_manager.normal(i).line_break()
        elif len(params) == 1:
            raise CommandException(params[0] + ' requires at least one parameter.')
        else:
            if params[0] == 'add':
                try:
                    self.functor(mole).add_filter(params[1], params[2:])
                except FilterNotFoundException:
                    raise CommandException('Filter ' + params[1] + ' not found.')
                except FilterCreationError as ex:
                    raise CommandException('Filter {0} failed to initialize({1})'.format(params[1], str(ex)))
            elif params[0] == 'del':
                self.functor(mole).remove_filter(params[1])
            else:
                raise CommandException('Parameter ' + params[1] + ' is not valid.')

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return ['add', 'del']
        elif len(current_params) == 1:
            if current_params[0] == 'add':
                return self.functor(mole).available_filters()
            elif current_params[0] == 'del':
                return self.functor(mole).active_filters()


class HTMLFilterCommand(BaseFilterCommand):

    def __init__(self):
        BaseFilterCommand.__init__(self, lambda mole: mole.requester.response_filters)

    def execute(self, mole, params):
        try:
            BaseFilterCommand.execute(self, mole, params)
        except FilterCreationError as ex:
            raise CommandException('Filter creation error({msg})'.format(msg=str(ex)), False)

class QueryFilterCommand(BaseFilterCommand):
    def __init__(self):
        BaseFilterCommand.__init__(self, lambda mole: mole.requester.query_filters)

    def execute(self, mole, params):
        try:
            BaseFilterCommand.execute(self, mole, params)
        except CommandException as ex:
            if len(params) > 1 and params[0] == 'config':
                if len(params) < 3:
                    raise CommandException('Expected more arguments.')
                try:
                    mole.requester.query_filters.config(params[1], params[2:])
                except FilterConfigException as ex:
                    output_manager.error('Filter config error({msg})'.format(msg=str(ex))).line_break()
                except FilterNotFoundException as ex:
                    output_manager.error('Filter {0} not found.'.format(params[1])).line_break()
            else:
                raise ex

    def parameters(self, mole, current_params):
        params = BaseFilterCommand.parameters(self, mole, current_params)

        if len(current_params) == 0:
            return params + ['config']
        if params is not None and len(params) > 0:
            return params
        if len(current_params) == 1:
            if current_params[0] == 'config':
                return mole.requester.query_filters.active_filters()
        elif current_params[0] == 'config':
            try:
                return mole.requester.query_filters.parameters(current_params[1], current_params[2:])
            except FilterNotFoundException:
                pass
        return []

    def usage(self, cmd_name):
        return cmd_name + ' (add|del|config) [FILTER_NAME [ARGS]]'

class ExportCommand(Command):
    def execute(self, mole, params):
        if len(params) != 2:
            raise CommandException('Expected type and filename as parameter')
        if params[0] not in ['xml']:
            raise CommandException('Unknown export format.')
        try:
            mole.export_xml(params[1])
            output_manager.advance('[+] Exportation successful')
        except FileOpenException:
            raise CommandException('The file given could not be opened', False)
        except NotInitializedException:
            raise CommandException('Mole must be initialized in order to export', False)

    def parameters(self, mole, current_params):
        return ['xml'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <format> <output_filename>'

class ImportCommand(Command):
    def execute(self, mole, params):
        if len(params) != 2:
            raise CommandException('Expected type and filename as parameter')
        if params[0] not in ['xml']:
            raise CommandException('Unknown import format.')
        try:
            mole.import_xml(params[1])
            output_manager.advance('Importation successful').line_break()
        except FileOpenException:
            raise CommandException('The file given could not be opened', False)
        except InvalidFormatException:
            raise CommandException('The file given has an invalid format', False)
        except InvalidDataException:
            raise CommandException('The file given has invalid data', False)

    def parameters(self, mole, current_params):
        return ['xml'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <format> <input_filename>'

class InjectableFieldCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            inj_field = mole.injectable_field
            if inj_field is None:
                output_manager.normal('No injectable field has been set yet').line_break()
            else:
                output_manager.normal(str(inj_field)).line_break()
        else:
            try:
                inj = int(params[0]) - 1
            except:
                raise CommandException('Expected integer as argument')
            if mole.set_injectable_field(inj):
                output_manager.advance('Injectable field changed successfully').line_break()
            else:
                output_manager.normal('Could not set the injectable field').line_break()

    def parameters(self, mole, current_params):
        return range(mole.query_columns)

    def usage(self, cmd_name):
        return cmd_name + ' [INJECTABLE_FIELD]'

class ReadFileCommand(Command):
    def execute(self, mole, params):
        self.check_initialization(mole)
        if len(params) != 1:
            raise CommandException('Expected filename as parameter')
        data = mole.read_file(params[0])
        if len(data) == 0:
            output_manager.error('Error reading file or file is empty.').line_break()
        else:
            output_manager.normal(data).line_break()

    def parameters(self, mole, current_params):
        return []

    def usage(self, cmd_name):
        return cmd_name + ' <filename>'

class MethodCommand(Command):
    accepted_methods = ['GET', 'POST', 'Cookie']

    def execute(self, mole, params):
        if len(params) == 0:
            method = mole.requester.method
            if method == 'POST':
                params = mole.requester.get_post_params()
            elif method == 'Cookie':
                params = mole.requester.get_cookie_params()
            else:
                params = mole.requester.get_get_params()
            if len(params) == 0:
                params = 'No parameters have been set.'
            output_manager.normal('{0}: {1}'.format(method, params)).line_break()
        elif len(params) >= 1:
            try:
                mole.set_method(params[0])
            except InvalidMethodException:
                raise CommandException('The method ' + params[0] + ' is not supported!')

            if len(params) >= 2:
                if params[0] == 'POST':
                    mole.set_post_params(params[1])
                elif params[0] == 'Cookie':
                    mole.set_cookie_params(params[1])
                elif params[0] == 'GET':
                    mole.set_get_params(params[1])

            if len(params) == 3:
                mole.set_vulnerable_param(params[0], params[2])

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return self.accepted_methods
        elif len(current_params) == 2:
            return list(t.split('=', 1)[0] for t in current_params[1].split('&'))
        else:
            return []


    def usage(self, cmd_name):
        return cmd_name + ' (GET | POST | Cookie) [PARAMS] [VULNERABLE_PARAM]'

class VulnerableParamCommand(Command):
    accepted_methods = ['GET', 'POST', 'Cookie']

    def execute(self, mole, params):
        if len(params) == 0:
            method, param = mole.requester.get_vulnerable_param()
            output_manager.normal('{0} {1}'.format(method, param)).line_break()
        elif len(params) == 2:
            if params[0] not in self.accepted_methods:
                raise CommandException('The method ' + params[0] + ' is not supported!')
            try:
                mole.set_vulnerable_param(params[0], params[1])
            except InvalidParamException:
                raise CommandException('Parameter given is not valid')
        else:
            raise CommandException('Expected vulnerable parameter')

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return self.accepted_methods
        if len(current_params) == 1:
            if current_params[0] == 'GET':
                return [x[0] for x in mole.requester.get_parameters]
            elif current_params[0] == 'POST':
                return [x[0] for x in mole.requester.post_parameters]
            elif current_params[0] == 'Cookie':
                return [x[0] for x in mole.requester.cookie_parameters]
        return []

    def usage(self, cmd_name):
        return cmd_name + ' (GET | POST | Cookie) <VULNERABLE_PARAM>'

class HTTPHeadersCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            max_len = max(map(len, mole.requester.headers.keys()))
            for key in mole.requester.headers:
                output_manager.normal('{0}{1}-> {2}'.format(key, ' ' * (max_len - len(key)), mole.requester.headers[key])).line_break()
        elif params[0] == 'set':
            if len(params) < 3:
                raise CommandException('"set" expects header key and value as arguments.')
            if params[1] == 'Cookie':
                CookieCommand().execute(mole, params[2:], output_manager)
            else:
                mole.requester.headers[params[1]] = ' '.join(params[2:])
        elif params[0] == 'del':
            if len(params) != 2:
                raise CommandException('"del" expects header key as argument.')
            del mole.requester.headers[params[1]]
        else:
            raise CommandException("Invalid argument.")

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return ['set', 'del']
        elif len(current_params) == 1:
            if current_params[0] in ['set', 'del']:
                return mole.requester.headers.keys()
        return []

    def usage(self, cmd_name):
        return cmd_name + ' [add|del] [NAME [VALUE]]'

class AuthCommand(Command):
    def execute(self, mole, params):
        if len(params) < 2:
            raise CommandException("Auth method and user credentials required.")
        if params[0] == 'basic':
            params = ' '.join(params[1:]).split(':')
            if len(params) < 2:
                raise CommandException("Missing password.")
            username = params[0]
            password = ':'.join(params[1:])
            mole.requester.headers["Authorization"] = "Basic " + b64encode((username + ':' + password).encode()).decode()
        else:
            raise CommandException("Invalid method")

    def parameters(self, mole, current_params):
        return ['basic'] if len(current_params) == 0 else []

    def usage(self, cmd_name):
        return cmd_name + ' <BASIC|DIGEST> USERNAME:PASSWORD'

class EncodingCommand(Command):
    def execute(self, mole, params):
        if len(params) == 0:
            if mole.requester.encoding is not None:
                output_manager.normal(mole.requester.encoding).line_break()
            else:
                output_manager.normal('No encoding set yet.').line_break()
        else:
            try:
                codecs.lookup(params[0])
            except LookupError:
                raise CommandException('Encoding ' + params[0] + ' does not exist.', False)
            mole.requester.encoding = params[0]

    def parameters(self, mole, current_params):
        return []

    def usage(self, cmd_name):
        return cmd_name + ' [ENCODING]'

class RecursiveCommand(Command):
    first_param = ['schemas', 'tables']

    def execute(self, mole, params):
        if len(params) == 0:
            raise CommandException('Recursive command needs at least an argument')
        if len(params) == 1 and params[0] not in self.first_param:
            raise CommandException('The first argument for the recursive command must be schemas or tables!')
        if len(params) == 1 and params[0] == 'tables':
            raise CommandException('Recursive command needs schema name if you are retrieving tables!')

        self.check_initialization(mole)

        if params[0] == 'schemas':
            self.__get_schemas(mole)
        elif params[0] == 'tables':
            self.__get_tables(mole, params[1])

    def parameters(self, mole, current_params):
        if len(current_params) == 0:
            return self.first_param
        if len(current_params) == 1 and current_params[0] == 'tables':
            schemas = mole.poll_databases()
            return schemas if schemas else []
        return []

    def usage(self, cmd_name):
        return cmd_name + ' (schemas | tables <schema>)'

    def __get_schemas(self, mole):
        schemas = mole.get_databases()
        for schema in schemas:
            output_manager.info('Starting dumping schema: {0}'.format(schema)).line_break()
            self.__get_tables(mole, schema)
            output_manager.info('Finished dumping schema: {0}'.format(schema)).line_break()

    def __get_tables(self, mole, schema):
        try:
            tables = mole.get_tables(schema)
        except QueryError as ex:
            output_manager.error("Failed fetching tables({0}).".format(ex)).line_break()
            return
        for table in tables:
            output_manager.info('Dumping table: {0} from schema: {1}'.format(table, schema)).line_break()
            try:
                mole.get_columns(schema, table)
            except QueryError as ex:
                output_manager.error("Error fetching columns({0}).".format(ex)).line_break()


class CommandManager:
    def __init__(self):
        self.cmds = {
                      'auth'     : AuthCommand(),
                      'clear'    : ClearScreenCommand(),
                      'columns'  : ColumnsCommand(),
                      'cookie'   : CookieCommand(),
                      'dbinfo'   : DBInfoCommand(),
                      'delay'    : DelayCommand(),
                      'encoding' : EncodingCommand(),
                      'exit'     : ExitCommand(),
                      'export'   : ExportCommand(),
                      'fetch'    : FetchDataCommand(),
                      'find_tables' : BruteforceTablesCommand(),
                      'find_tables_like' : FindTablesLikeCommand(),
                      'find_users_table'  : BruteforceUserTableCommand(),
                      'follow_redirects' : RedirectCommand(),
                      'headers'  : HTTPHeadersCommand(),
                      'htmlfilter'  : HTMLFilterCommand(),
                      'import'   : ImportCommand(),
                      'injectable_field' : InjectableFieldCommand(),
                      'method'   : MethodCommand(),
                      'mode'     : QueryModeCommand(),
                      'needle'   : NeedleCommand(),
                      'output'   : OutputCommand(),
                      'prefix'   : PrefixCommand(),
                      'query'    : QueryCommand(),
                      'qfilter'  : QueryFilterCommand(),
                      'readfile' : ReadFileCommand(),
                      'recursive': RecursiveCommand(),
                      'schemas'  : SchemasCommand(),
                      'suffix'   : SuffixCommand(),
                      'tables'   : TablesCommand(),
                      'url'      : URLCommand(),
                      'usage'    : UsageCommand(),
                      'usercreds' : UserCredentialsCommand(),
                      'verbose'  : VerboseCommand(),
                      'vulnerable_param' : VulnerableParamCommand(),
                    }

    def find(self, cmd):
        if cmd in self.cmds:
            return self.cmds[cmd]
        else:
            raise CmdNotFoundException(cmd + ' is not a valid command')

    def commands(self):
        return self.cmds.keys()
