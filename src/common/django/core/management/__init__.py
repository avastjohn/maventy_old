import os
import sys
from optparse import OptionParser
import imp

import django
from django.core.management.base import BaseCommand, CommandError, handle_default_options

# For backwards compatibility: get_version() used to be in this module.
get_version = django.get_version

# A cache of loaded commands, so that call_command
# doesn't have to reload every time it's called.
_commands = None

def find_commands(management_dir):
    """
    Given a path to a management directory, returns a list of all the command
    names that are available.

    This implementation also works when Django is loaded from a zip file.

    Returns an empty list if no commands are defined.
    """
    zip_marker = '.zip' + os.sep
    command_dir = os.path.join(management_dir, 'commands')
    if zip_marker not in command_dir:
        return original_find_commands(command_dir)

    import zipfile
    # Django is sourced from a zipfile, ask zip module for a list of files.
    filename, path = command_dir.split(zip_marker)
    zipinfo = zipfile.ZipFile(filename + '.zip')

    # The zipfile module returns paths in the format of the operating system
    # that created the zipfile! This may not match the path to the zipfile
    # itself. Convert operating system specific characters to '/'.
    path = path.replace('\\', '/')
    def _IsCmd(t):
        """Returns true if t matches the criteria for a command module."""
        t = t.replace('\\', '/')
        return t.startswith(path) and not os.path.basename(t).startswith('_') \
            and t.endswith('.py')

    return [os.path.basename(f)[:-3] for f in zipinfo.namelist() if _IsCmd(f)]

def original_find_commands(command_dir):
    """
    Given a path to a management directory, returns a list of all the command
    names that are available.

    Returns an empty list if no commands are defined.
    """
    try:
        return [f[:-3] for f in os.listdir(command_dir)
                if not f.startswith('_') and f.endswith('.py')]
    except OSError:
        return []

def find_management_module(app_name):
    """
    Determines the path to the management module for the given app_name,
    without actually importing the application or the management module.

    Raises ImportError if the management module cannot be found for any reason.
    """
    parts = app_name.split('.')
    parts.append('management')
    parts.reverse()
    part = parts.pop()
    path = None

    # When using manage.py, the project module is added to the path,
    # loaded, then removed from the path. This means that
    # testproject.testapp.models can be loaded in future, even if
    # testproject isn't in the path. When looking for the management
    # module, we need look for the case where the project name is part
    # of the app_name but the project directory itself isn't on the path.
    return os.path.dirname(__import__(app_name + '.management',
                                      {}, {}, ['']).__file__)

def load_command_class(app_name, name):
    """
    Given a command name and an application name, returns the Command
    class instance. All errors raised by the import process
    (ImportError, AttributeError) are allowed to propagate.
    """
    return getattr(__import__('%s.management.commands.%s' % (app_name, name),
                   {}, {}, ['Command']), 'Command')()

def get_commands():
    """
    Returns a dictionary mapping command names to their callback applications.

    This works by looking for a management.commands package in django.core, and
    in each installed application -- if a commands package exists, all commands
    in that package are registered.

    Core commands are always included. If a settings module has been
    specified, user-defined commands will also be included, the
    startproject command will be disabled, and the startapp command
    will be modified to use the directory in which the settings module appears.

    The dictionary is in the format {command_name: app_name}. Key-value
    pairs from this dictionary can then be used in calls to
    load_command_class(app_name, command_name)

    If a specific version of a command must be loaded (e.g., with the
    startapp command), the instantiated module can be placed in the
    dictionary in place of the application name.

    The dictionary is cached on the first call and reused on subsequent
    calls.
    """
    global _commands
    if _commands is None:
        _commands = dict([(name, 'django.core') for name in find_commands(__path__[0])])

        # Find the installed apps
        try:
            from django.conf import settings
            apps = settings.INSTALLED_APPS
        except (AttributeError, EnvironmentError, ImportError):
            apps = []

        # Find the project directory
        try:
            from django.conf import settings
            project_directory = setup_environ(
                __import__(
                    settings.SETTINGS_MODULE, {}, {},
                    (settings.SETTINGS_MODULE.split(".")[-1],)
                ), settings.SETTINGS_MODULE
            )
        except (AttributeError, EnvironmentError, ImportError):
            project_directory = None

        # Find and load the management module for each installed app.
        for app_name in apps:
            try:
                path = find_management_module(app_name)
                _commands.update(dict([(name, app_name)
                                       for name in find_commands(path)]))
            except ImportError:
                pass # No management module - ignore this app

        if project_directory:
            # Remove the "startproject" command from self.commands, because
            # that's a django-admin.py command, not a manage.py command.
            del _commands['startproject']

            # Override the startapp command so that it always uses the
            # project_directory, not the current working directory
            # (which is default).
            from django.core.management.commands.startapp import ProjectCommand
            _commands['startapp'] = ProjectCommand(project_directory)

    return _commands

def call_command(name, *args, **options):
    """
    Calls the given command, with the given options and args/kwargs.

    This is the primary API you should use for calling specific commands.

    Some examples:
        call_command('syncdb')
        call_command('shell', plain=True)
        call_command('sqlall', 'myapp')
    """
    try:
        app_name = get_commands()[name]
        if isinstance(app_name, BaseCommand):
            # If the command is already loaded, use it directly.
            klass = app_name
        else:
            klass = load_command_class(app_name, name)
    except KeyError:
        raise CommandError, "Unknown command: %r" % name
    return klass.execute(*args, **options)

class LaxOptionParser(OptionParser):
    """
    An option parser that doesn't raise any errors on unknown options.

    This is needed because the --settings and --pythonpath options affect
    the commands (and thus the options) that are available to the user.
    """
    def error(self, msg):
        pass

    def print_help(self):
        """Output nothing.

        The lax options are included in the normal option parser, so under
        normal usage, we don't need to print the lax options.
        """
        pass

    def print_lax_help(self):
        """Output the basic options available to every command.

        This just redirects to the default print_help() behaviour.
        """
        OptionParser.print_help(self)

    def _process_args(self, largs, rargs, values):
        """
        Overrides OptionParser._process_args to exclusively handle default
        options and ignore args and other options.

        This overrides the behavior of the super class, which stop parsing
        at the first unrecognized option.
        """
        while rargs:
            arg = rargs[0]
            try:
                if arg[0:2] == "--" and len(arg) > 2:
                    # process a single long option (possibly with value(s))
                    # the superclass code pops the arg off rargs
                    self._process_long_opt(rargs, values)
                elif arg[:1] == "-" and len(arg) > 1:
                    # process a cluster of short options (possibly with
                    # value(s) for the last one only)
                    # the superclass code pops the arg off rargs
                    self._process_short_opts(rargs, values)
                else:
                    # it's either a non-default option or an arg
                    # either way, add it to the args list so we can keep
                    # dealing with options
                    del rargs[0]
                    raise error
            except:
                largs.append(arg)

class ManagementUtility(object):
    """
    Encapsulates the logic of the django-admin.py and manage.py utilities.

    A ManagementUtility has a number of commands, which can be manipulated
    by editing the self.commands dictionary.
    """
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]
        self.prog_name = os.path.basename(self.argv[0])

    def main_help_text(self):
        """
        Returns the script's main help text, as a string.
        """
        usage = ['',"Type '%s help <subcommand>' for help on a specific subcommand." % self.prog_name,'']
        usage.append('Available subcommands:')
        commands = get_commands().keys()
        commands.sort()
        for cmd in commands:
            usage.append('  %s' % cmd)
        return '\n'.join(usage)

    def fetch_command(self, subcommand):
        """
        Tries to fetch the given subcommand, printing a message with the
        appropriate command called from the command line (usually
        "django-admin.py" or "manage.py") if it can't be found.
        """
        try:
            app_name = get_commands()[subcommand]
            if isinstance(app_name, BaseCommand):
                # If the command is already loaded, use it directly.
                klass = app_name
            else:
                klass = load_command_class(app_name, subcommand)
        except KeyError:
            sys.stderr.write("Unknown command: %r\nType '%s help' for usage.\n" % \
                (subcommand, self.prog_name))
            sys.exit(1)
        return klass

    def execute(self):
        """
        Given the command-line arguments, this figures out which subcommand is
        being run, creates a parser appropriate to that command, and runs it.
        """
        # Preprocess options to extract --settings and --pythonpath.
        # These options could affect the commands that are available, so they
        # must be processed early.
        parser = LaxOptionParser(usage="%prog subcommand [options] [args]",
                                 version=get_version(),
                                 option_list=BaseCommand.option_list)
        try:
            options, args = parser.parse_args(self.argv)
            handle_default_options(options)
        except:
            pass # Ignore any option errors at this point.

        try:
            subcommand = self.argv[1]
        except IndexError:
            sys.stderr.write("Type '%s help' for usage.\n" % self.prog_name)
            sys.exit(1)

        if subcommand == 'help':
            if len(args) > 2:
                self.fetch_command(args[2]).print_help(self.prog_name, args[2])
            else:
                parser.print_lax_help()
                sys.stderr.write(self.main_help_text() + '\n')
                sys.exit(1)
        # Special-cases: We want 'django-admin.py --version' and
        # 'django-admin.py --help' to work, for backwards compatibility.
        elif self.argv[1:] == ['--version']:
            # LaxOptionParser already takes care of printing the version.
            pass
        elif self.argv[1:] == ['--help']:
            parser.print_lax_help()
            sys.stderr.write(self.main_help_text() + '\n')
        else:
            self.fetch_command(subcommand).run_from_argv(self.argv)

def setup_environ(settings_mod, original_settings_path=None):
    """
    Configures the runtime environment. This can also be used by external
    scripts wanting to set up a similar environment to manage.py.
    Returns the project directory (assuming the passed settings module is
    directly in the project directory).

    The "original_settings_path" parameter is optional, but recommended, since
    trying to work out the original path from the module can be problematic.
    """
    # Add this project to sys.path so that it's importable in the conventional
    # way. For example, if this file (manage.py) lives in a directory
    # "myproject", this code would add "/path/to/myproject" to sys.path.
    project_directory, settings_filename = os.path.split(settings_mod.__file__)
    if project_directory == os.curdir or not project_directory:
        project_directory = os.getcwd()
    project_name = os.path.basename(project_directory)
    settings_name = os.path.splitext(settings_filename)[0]
    sys.path.append(os.path.join(project_directory, os.pardir))
    project_module = __import__(project_name, {}, {}, [''])
    sys.path.pop()

    # Set DJANGO_SETTINGS_MODULE appropriately.
    if original_settings_path:
        os.environ['DJANGO_SETTINGS_MODULE'] = original_settings_path
    else:
        os.environ['DJANGO_SETTINGS_MODULE'] = '%s.%s' % (project_name, settings_name)
    return project_directory

def execute_from_command_line(argv=None):
    """
    A simple method that runs a ManagementUtility.
    """
    utility = ManagementUtility(argv)
    utility.execute()

def execute_manager(settings_mod, argv=None):
    """
    Like execute_from_command_line(), but for use by manage.py, a
    project-specific django-admin.py utility.
    """
    setup_environ(settings_mod)
    utility = ManagementUtility(argv)
    utility.execute()