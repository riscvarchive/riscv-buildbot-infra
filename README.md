riscv-buildbot-infra
====================

This repository contains a buildbot configuration file that runs a
number of RISC-V projects.  The general idea here is to keep
everything in one place so it's easier for people to duplicate this
setup on their own machines, when running the code they care about.

Installation
------------

This repository contains a buildbot configuration that watches the
various publicly availiable RISC-V related projects master branches on
http://github.com/riscv and builds them whenever there are changes.
It is also configured to run nightly builds of all these projects, to
ensure infrequently changed projects still get tested regularly.

While this repository alone doesn't contain a full buildbot
configuration, it is fairly close.  In order to get up and running,
you need to do the following things:

* Install builtbot-master and buildbot-slave

* Initialize your builtbot-master and builtbot-slave directories

* Clone this repository into buildbot-master's directory.  Something
  like

````
cd buildmaster
git clone git://github.com/riscv/riscv-buildbot-infra.git
mv riscv-buildbot-infra/.git .
rm -rf riscv-buildbot-infra
git reset --hard origin/master
````

  should suffice.

* Add configuration files for each of your buildslave instances.  An
  example configuration can be seen at
  "config/slaves/palmer-farm001.dabbelt.com.json.example".
  "config/slaves/*.json" are loaded, everything else is ignored.  Be
  sure not to put your passwords in a publicly availiable git repo!

* Add a report configuration to send email on build failures.

* Ensure the buildmaster and buildslaves are running.

Adding Projects
---------------

This repository is designed to make adding new projects as simple as
possible.  Project configuration JSON files are located at
"config/projects/".  While you shouldn't have to modify the project
files get a RISC-V buildbot instance up and running, you will have to
modify them in order to build projects you care about -- which is kind
of the whole point of running your own buildbot :).

The best way to create a new project is to copy an existing one and
modify it to your needs.  "riscv-gnu-toolchain.json" was the first
project that was created, so it's probably the one that fits this
model most stright-forwardly.  The project JSON files are configured
as follows:

name
    : The project's name, used only for frontend-related things
url
    : The git URL that contains the main source for this repository.
    This URL will be polled for changes.
configurations
    : Details about the various configurations that a project can be
    built in, as well as the list of commands involved in building
    each of those configurations.

### The Configurations List ###

The most complicated part of a project is the configuration list.
This format was designed in order to make building different
configurations of the same source base easy -- this is something that
would take a lot of code writing in a generic buildbot setup.
Configurations consist of the following keys

name
    : A pattern that describes how the name of this configuration will
    be constructed from each elaborated parameter list.
parameters
    : A list of parameters along with the values that they can take
    on.  These are listed as a pair, with "pattern" being the name of
    the parameter and "values" being an array of values the parameter
    can take on.
steps
   : The list of steps involved in building a particular
   configuration.

The rule for elaborating configurations is pretty straight-forward:

* The Cartesian product of all the paramaters is produced, producing a
  set of "pattern"->"value" maps.

* For each "pattern"->"value" map, a regular expression along the set
  of "pattern"->"value" mapslines of "s/name/value/" is run on "name"
  and each element of the "steps" array.

For example, the following configuration

````
{
  "name": "riscv@xlen@-unknown-@libc@",
  "parameters": [
    {
      "pattern": "@xlen@",
      "values": ["32", "64", "128"]
    },
    {
      "pattern": "@libc@",
      "values": ["elf", "linux-gnu"]
    },
  ]
}
````

will elaborate to

````
riscv32-unknown-elf
riscv32-unknown-linux-gnu
riscv64-unknown-elf
riscv64-unknown-linux-gnu
riscv128-unknown-elf
riscv128-unknown-linux-gnu
````

which is a useful set if you're trying to test all the --target tuples
we care about.  More examples can be seen in the various configuration
files.
