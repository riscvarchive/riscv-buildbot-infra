# This first part of the file reads the RSIC-V buildbot configuration
# files (located in config/), and produces an in-memory representation
# of the configuration file that's suitable for emission as a buildbot
# configuration.  The second half of the file then goes and walks
# through this information and produces a buildbot configuration so
# buildbot can actually run.
import itertools
import json
import os
import re
import sys

# This class represents a single slave, which just stores some
# configuration information about that slave.
class Slave:
    def __init__(self, config):
        self._hostname = config["hostname"]
        self._password = config["password"]
        self._features = config["features"]

    def hostname(self):
        return self._hostname

    def password(self):
        return self._password

# Stores the entire list of slaves, 
class SlaveList:
    def __init__(self, directory):
        self._slaves = list()

        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                print "Loading slave config " + filename
                lines = open(directory + filename).read()
                slave = Slave(json.loads(lines))
                self._slaves.append(slave)

    def slaves(self):
        return self._slaves

# Contains a pattern that will be replaced in things like the
# configuration/target names -- this is just a little helper that
# provides names to the pattern/value mappings.
class Parameter:
    def __init__(self, pattern, value):
        self.pattern = pattern
        self.value = value

    def __str__(self):
        return "s!" + self.pattern + "!" + self.value + "!"

    def replace(self, source):
        return re.sub(self.pattern, self.value, source)
                
# Stores a single target, which is the sort of thing that will end up
# being built.  A project can form many of these if it has a lot of
# different parameters -- it's essentially the cartesian product of
# all the parameter values in a particular entry in a project's
# configuration list.  You can't directly create a target from the
# JSON file.
class Target:
    def __init__(self, name, branch, steps, params):
        self._name = name
        self._branch = branch
        self._steps = steps
        self._params = params

    def replaceall(self, source):
        for param in self._params:
            source = param.replace(source)
        return source

    def name(self):
        return self.replaceall(self._name)

    def branch(self):
        return self._branch

    def steps(self):
        return map(lambda step: map(lambda argv: self.replaceall(argv),
                                    step),
                   self._steps)

    def find_matching_slaves(self, slave_list):
        return slave_list.slaves()

# Stores a project, which consists of many targets.  This class is
# responsible for the logic that converts a 
class Project:
    def __init__(self, config):
        self._name = config["name"]
        self._url = config["url"]

        # First we build up the list of targets -- note that these
        # aren't quite fully-fledged yet, as they don't have things
        # like the set of features that are required in order to build
        # them,
        self._targets = list()
        for configuration in config["configurations"]:
            name = configuration["name"]
            branch = configuration["branch"] if 'branch' in configuration else "master"
            steps = configuration["steps"]

            parameters = list()
            for parameter in configuration["parameters"]:
                pvpairs = list()
                pattern = parameter["pattern"]
                for value in parameter["values"]:
                    pvpairs.append(Parameter(pattern, value))
                parameters.append(pvpairs)

            for params in itertools.product(*parameters):
                target = Target(name, branch, steps, params)
                self._targets.append(target)

    def name(self):
        return self._name

    def url(self):
        return self._url

    def targets(self):
        return self._targets

    def target_name(self, target):
        return self.name() + "@" + target.name()

    def all_target_names(self):
        return map(lambda target: self.target_name(target),
                   self.targets())

# The list of all projects, pretty much just a way to collect them all
# somewhere in a way that parses its own directory format.
class ProjectList:
    def __init__(self, directory):
        self._projects = list()

        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                print "Loading project config " + filename
                lines = open(directory + filename).read()
                project = Project(json.loads(lines))
                self._projects.append(project)

    def projects(self):
        return self._projects

    def targets(self):
        for project in self.projects():
            for target in project.targets():
                yield target

# Contains the list of status reports that should be installed
class Report:
    def __init__(self, config):
        self._type     = config["type"]
        if self.type() == "email":
            self._faddr    = config["from"]
            self._username = config["username"]
            self._password = config["password"]
            self._relay    = config["relay"]
        elif self.type() == "http":
            self._port     = config["port"]
        else:
            print "Unknown report type " + self.type()
            abort

    def type(self):
        return self._type

    def faddr(self):
        return self._faddr

    def username(self):
        return self._username

    def password(self):
        return self._password

    def relay(self):
        return self._relay

    def port(self):
        return int(self._port)

class ReportList:
    def __init__(self, directory):
        self._reports = list()

        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                print "Loading report config " + filename
                lines = open(directory + filename).read()
                report = Report(json.loads(lines))
                self._reports.append(report)

    def reports(self):
        return self._reports

class ForceList:
    def __init__(self, filename):
        self._forces = list()

        print "Loading force config " + filename
        lines = open(filename).read()
        projects = json.loads(lines)
        self._forces = projects["projects"]

    def should_force(self, project_name):
        if self._forces == "*":
            return True
        return project_name in self._forces

slave_list = SlaveList("config/slaves/")
project_list = ProjectList("config/projects/")
report_list = ReportList("config/reports/")
force_list = ForceList("config/force.json")

for report in report_list.reports():
    if report.type() == "email":
        print "report " + report.faddr()
    if report.type() == "http":
        print "report " + str(report.port())

for target in project_list.targets():
    print "target " + target.name()
    for match in target.find_matching_slaves(slave_list):
        print "  " + match.hostname()

# Now comes the second half of the configuration file, which produces
# something the buildbot can actually use by reading the configuration
# files that were built by the top half.
from buildbot.status.html import WebStatus
from buildbot.changes.gitpoller import GitPoller
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.basic import SingleBranchScheduler
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.changes.filter import ChangeFilter
from buildbot.steps.source import Git
from buildbot.steps.shell import ShellCommand
from buildbot.schedulers.timed import Nightly
from buildbot.status.mail import MailNotifier
from buildbot.status.web import authz

c = BuildmasterConfig = {}

c['title'] = "riscv-buildbot.dabbelt.com"
c['titleURL'] = "http://riscv-buildbot.dabbelt.com"
c['buildbotURL'] = "http://riscv-buildbot.dabbelt.com"

authz_cfg=authz.Authz(
  forceBuild = True
)

c['protocols'] = {'pb': {'port': 9989}}

# buildbot requires a flatened format for all its configuration
# entries, with some strings that serve as links between the various
# sections.  This builds up that format.
c['status'] = []
c['change_source'] = []
c['slaves'] = []
c['builders'] = []
c['schedulers'] = []

# slaves don't have any links at all, so they're pretty
# stright-forward -- we just output the whole list of slaves.
for slave in slave_list.slaves():
    c['slaves'].append(
        BuildSlave(
            slave.hostname(),
            slave.password(),
            max_builds=2
        )
    )

# builders map directly to targets, but since targets don't have everything
for project in project_list.projects():
    for target in project.targets():
        fact = BuildFactory()
        fact.addStep(Git(repourl = project.url(),
                         branch  = target.branch(),
                         mode    = "clobber"
                     )
                 )
        for step in target.steps():
            fact.addStep(ShellCommand(command=step,
                                      timeout=(10 * 60 * 60)
                                  )
                     )

        slaves = map(
            lambda s: s.hostname(),
            target.find_matching_slaves(slave_list)
        )

        c['builders'].append(
            BuilderConfig(
                name       = project.target_name(target),
                slavenames = slaves,
                factory    = fact
            )
        )
                
# Schedulers are a per-project entity, but need to contain the list of
# every target that they build.  First we define the nightly target,
# which doesn't actually depend on anything that does any polling.
for project in project_list.projects():
    c['schedulers'].append(
        Nightly(
            name         = "sched-nightly-" + project.name(),
            branch       = "master",
            builderNames = project.all_target_names(),
            hour         = 00,
            minute       = 52
        )
    )
    if force_list.should_force(project.name()):
        c['schedulers'].append(
            ForceScheduler(
                name = ("force-" + project.name()).encode('ascii','ignore'),
                builderNames = map(
                    lambda n: n.encode('ascii','ignore'),
                    project.all_target_names())
            )
        )

# Installs email handlers
for report in report_list.reports():
    if report.type() == "email":
        c['status'].append(
            MailNotifier(
                mode                  = ('failing',),
                fromaddr              = report.faddr(),
                sendToInterestedUsers = True,
                relayhost             = report.relay(),
                smtpPort              = 587,
                smtpUser              = report.username(),
                smtpPassword          = report.password(),
                )
            )

    if report.type() == "http":
        authz_cfg = authz.Authz(forceBuild = True)
        c['status'].append(
            WebStatus(report.port(), authz=authz_cfg)
            )
