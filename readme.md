# ChannelRepositoryTools

A Sublime Text package for working with channels and repositories. Functionality
includes:

 - Testing the default channel
 - Testing a local repository JSON file
 - Testing a remote repository JSON URL
 - Upgrading a local repository JSON file

## Installation

Installation is performed via Package Control.

## Usage

This package was designed to work with the default Package Control channel.
Before using this package, it is necessary to:

 1. Fork https://github.com/wbond/package_control_channel
 2. Clone your fork of package_control_channel using Git
 3. Open package_control_channel in Sublime Text

### Testing the Default Channel

Most users will want to open the command palette and type:

**ChannelRepositoryTools: Test Default Channel**

This will test the channel and the main repository.

### Testing the Default Channel with Remote Repositories

If you are working on cleaning up the default channel and making sure everything
is in good shape, you‘ll want to run the full test suite on the channel and
all remote repositories that are `schema_version` `2.0` or newer:

**ChannelRepositoryTools: Test Default Channel (including Remote Repositories)**

Repositories running an older version of the schema will not be tested, but
should be upgraded to the newest version by following the instructions in
the *Upgrading a Repository JSON File* section.

### Testing a Repository via URL

To test a repository hosted on a publicly-accessible URL, run the command:

**ChannelRepositoryTools: Test Remote Repository**

You will be prompted to enter the URL of the repository. The JSON file will be
downloaded and tested against the test suite.

### Testing a Repository via a File

To test a repository JSON file on your machine, open it in Sublime Text and
run the command:

**ChannelRepositoryTools: Test Local Repository (Current File)**

### Upgrading a Repository JSON File

If you open a repository JSON file in Sublime Text, you can upgrade it from
`schema_version` `1.0`, `1.1` or `1.2` by running the command:

**ChannelRepositoryTools: Upgrade Repository Schema (Current File)**

This will update the JSON to `schema_version` `2.0`. You may be prompted with
some additional information, such as instructions to create a tag via GitHub
or BitBucket.

You very likely will also be told that your package information should be moved
into the default repository which is part of the default channel. The repository
is made up of the JSON files in the `/repository/` folder of the
`package_control_channel`.

Most users who has custom `packages.json` files did so because of limitations to
older versions of Package Control. With `schema_version` `2.0` it is now
possible to limit packages to specific operating system and more without
maintaining your own `packages.json` file.

The new method has all details located in the repository, and new releases are
created by you making tags in your repository. As long as a tag is in the form
`MAJOR.MINOR.PATCH` (a [SemVer verison number](http://semver.org/)), Package
Control will automatically find it the next time your repo is crawled. It will
then be made available to users.

Whenever possible, please take the time to move your package into the default
repository so that the crawler can more efficiently check packages for updates.
