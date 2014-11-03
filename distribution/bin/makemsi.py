#!/usr/bin/env python
# -*- coding: utf-8 -*-
# **********************************************************************
#
# Copyright (c) 2003-2014 ZeroC, Inc. All rights reserved.
#
# This copy of Ice is licensed to you under the terms described in the
# ICE_LICENSE file included in this distribution.
#
# **********************************************************************

import os, sys, fnmatch, re, getopt, atexit, shutil, subprocess, zipfile, time, stat

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib")))


#
# Replace cpp/src/Makefile.mak with this to just build slice2cpp when building
# WinRT SDKs
#
winrtMakefile = \
"""
top_srcdir  = ..

!include $(top_srcdir)/config/Make.rules.mak

!if "$(WINRT)" == "yes"
SUBDIRS     = IceUtil\winrt \\
          Ice\winrt \\
          Glacier2Lib\winrt \\
          IceStormLib\winrt \\
          IceGridLib\winrt
!else
SUBDIRS     = IceUtil \\
          Slice \\
          slice2cpp \\
!endif

$(EVERYTHING)::
    @for %i in ( $(SUBDIRS) ) do \\
        @if exist %i \\
            @echo "making $@ in %i" && \\
            cmd /c "cd %i && $(MAKE) -nologo -f Makefile.mak $@" || exit 1
"""

#
# Files from debug builds that are not included in the installers.
#
debugFilterFiles = ["dumpdb.exe",
                    "glacier2router.exe",
                    "iceboxadmin.exe",
                    "icegridadmin.exe",
                    "icegridnode.exe",
                    "icegridregistry.exe",
                    "icepatch2calc.exe",
                    "icepatch2client.exe",
                    "icepatch2server.exe",
                    "iceserviceinstall.exe",
                    "icestormadmin.exe",
                    "icestormmigrate.exe",
                    "slice2cpp.exe",
                    "slice2cs.exe",
                    "slice2freeze.exe",
                    "slice2freezej.exe",
                    "slice2html.exe",
                    "slice2java.exe",
                    "slice2js.exe",
                    "slice2php.exe",
                    "slice2py.exe",
                    "slice2rb.exe",
                    "transformdb.exe",
                    "dumpdb.pdb",
                    "glacier2router.pdb",
                    "iceboxadmin.pdb",
                    "icegridadmin.pdb",
                    "icegridnode.pdb",
                    "icegridregistry.pdb",
                    "icepatch2calc.pdb",
                    "icepatch2client.pdb",
                    "icepatch2server.pdb",
                    "iceserviceinstall.pdb",
                    "icestormadmin.pdb",
                    "icestormmigrate.pdb",
                    "slice2cpp.pdb",
                    "slice2cs.pdb",
                    "slice2freeze.pdb",
                    "slice2freezej.pdb",
                    "slice2html.pdb",
                    "slice2java.pdb",
                    "slice2js.pdb",
                    "slice2php.pdb",
                    "slice2py.pdb",
                    "slice2rb.pdb",
                    "transformdb.pdb"]

def filterDebugFiles(f):
    if f in debugFilterFiles:
        return True
    if os.path.splitext(f)[1] in [".exe", ".dll", ".pdb"]:
        return False
    return True


from BuildUtils import *
from DistUtils import *

def runCommand(cmd, verbose):
    if len(cmd) > 0:
        if verbose:
            print(cmd)
        if os.system(cmd) != 0:
            sys.exit(1)

#signCommand = "signtool sign /f \"%s\" /p %s /t http://timestamp.verisign.com/scripts/timstamp.dll %s"

global signTool
global certFile
global certPassword


def sign(f, name = None):
    command = [signTool, 
               "sign", 
               "/f" , certFile, 
               "/p", certPassword,
               "/t", "http://timestamp.verisign.com/scripts/timstamp.dll"]
    if name != None:
        command += ["/d", name]
    command += [f]

    if subprocess.check_call(command) != 0:
        return False
    return True


def _handle_error(fn, path, excinfo):  
    print("error removing %s" % path)
    os.chmod(path, stat.S_IWRITE)
    fn(path)

def setMakefileOption(filename, optionName, value):
    optre = re.compile("^\#?\s*?%s\s*?=.*" % optionName)
    if os.path.exists(filename + ".tmp"):
        os.remove(filename + ".tmp")
    new = open(filename + ".tmp", "w")
    old = open(filename, "r")
    for line in old:
        if optre.search(line):
            new.write("%s = %s\n" % (optionName, value))
        else:
            new.write(line)
    old.close()
    new.close()
    shutil.move(filename + ".tmp", filename)

def overwriteFile(filename, data):
    f = open(filename, "w")
    f.write(data)
    f.close()

def executeCommand(command, env, verbose = True):
    if verbose:
        print(command)
    p = subprocess.Popen(command, shell = True, stdin = subprocess.PIPE, stdout = subprocess.PIPE, \
                         stderr = subprocess.STDOUT, bufsize = 0, env = env)

    if p:
        while(True):
            c = p.stdout.read(1)
            
            if not c:
                if p.poll() is not None:
                    break
                time.sleep(0.1)
                continue

            if type(c) != str:
                c = c.decode()
            
            sys.stdout.write(c)
        
        if p.poll() != 0:
            #
            # Command failed
            #
            print("Command failed exit status %s" % p.poll())
            sys.exit(1)

def relPath(sourceDir, targetDir, f):
    sourceDir = os.path.normpath(sourceDir)
    targetDir = os.path.normpath(targetDir)
    f = os.path.normpath(f)
    if f.find(sourceDir) == 0:
        f =  os.path.join(targetDir, f[len(sourceDir) + 1:])
    return f

def copyIfModified(source, target, verbose):
    if not os.path.exists(target) or os.path.getmtime(source) > os.path.getmtime(target):
        copy(source, target, verbose = verbose)
        if (target.endswith(".exe") or target.endswith(".dll") or target.endswith(".so")):
            if not sign(target):
                os.remove(target)
                sys.exit(1)
#
# Program usage.
#
def usage():
    print("")
    print(r"Options:")
    print("")
    print(r"  --help                      Show this message.")
    print("")
    print(r"  --verbose                   Be verbose.")
    print("")
    print(r"  --proguard-home=<path>      Proguard location, default location")
    print(r"                              is C:\proguard")
    print("")
    print(r"  --php-home=<path>           PHP source location, default location")
    print(r"                              is C:\php-5.6.1")
    print("")
    print(r"  --php-bin-home=<path>       PHP binaries location, default location")
    print(r"                              is C:\Program Files (x86)\PHP")
    print("")
    print(r"  --ruby-x86-home             Ruby location, default location is")
    print(r"                              C:\Ruby21")
    print("")
    print(r"  --ruby-amd64-home           Ruby location, default location is")
    print(r"                              C:\Ruby21-x64")
    print("")
    print(r"  --ruby-devkit-x86-home      Ruby DevKit location, default location is")
    print(r"                              C:\DevKit-mingw64-32-4.7.3")
    print("")
    print(r"  --ruby-devkit-amd64-home    Ruby DevKit location, default location is")
    print(r"                              C:\DevKit-mingw64-64-4.7.2")
    print("")
    print(r"  --nodejs-home               NodeJS location, default location is")
    print(r"                              C:\Program Files (x86)\nodejs")
    print("")
    print(r"  --gzip-home                 Gzip location, default location is")
    print(r"                              C:\Program Files (x86)\GnuWin32")
    print("")
    print(r"  --closure-home              Google closure compiler location, default location is")
    print(r"                              C:\closure")
    print("")
    print(r"  --skip-build                Skip build and go directly to installer creation,")
    print(r"                              existing build will be used")
    print("")
    print(r"  --skip-installer            Skip the installer creation, just do the build")
    print("")
    print(r"  --filter-languages=<name>   Just build and run the given languages")
    print("")
    print(r"  --filter-compilers=<name>   Just build the given compilers")
    print("")
    print(r"  --filter-archs=<name>       Just build the given architectures")
    print("")
    print(r"  --filter-confs=<name>       Just build the given configurations")
    print("")
    print(r"  --filter-profiles=<name>    Just build the given profiles")
    print("")
    print(r"  --cert-file=<path>          Certificate file used to sign the installer")
    print("")
    print(r"  --key-file=<path>           Key file used to sign the .NET Assemblies")
    print("")
    print(r"  --winrt                     Build WinRT SDKs installer")
    print("")

version = "3.6b"
verbose = False

args = None
opts = None

proguardHome = None
phpHome = None
phpBinHome = None
rubyHome = None
rubyX86Home = None
rubyAmd64Home = None
rubyDevKitHome = None
rubyDevKitX86Home = None
rubyDevKitAmd64Home = None
nodejsHome = None
nodejsExe = None
gzipHome = None
gzipExe = None
closureHome = None
skipBuild = False
skipInstaller = False

filterLanguages = []
filterCompilers = []
filterArchs = []
filterConfs = []
filterProfiles = []

rFilterLanguages = []
rFilterCompilers = []
rFilterArchs = []
rFilterConfs = []
rFilterProfiles = []

signTool = None
certFile = None
certPassword = None
keyFile = None
winrt = False

try:
    opts, args = getopt.getopt(sys.argv[1:], "", ["help", "verbose", "proguard-home=", "php-home=", "php-bin-home=",
                                                  "ruby-x86-home=", "ruby-amd64-home=", "ruby-devkit-x86-home=", 
                                                  "ruby-devkit-amd64-home=", "nodejs-home", "gzip-home", "closure-home", 
                                                  "skip-build", "skip-installer", "filter-languages=", 
                                                  "filter-compilers=", "filter-archs=","filter-confs=", 
                                                  "filter-profiles=", "filter-languages=", "filter-compilers=", 
                                                  "filter-archs=", "filter-confs=", "filter-profiles=", "sign-tool=", 
                                                  "cert-file=", "cert-password=", "key-file=", "winrt"])
except getopt.GetoptError as e:
    print("Error %s " % e)
    usage()
    sys.exit(1)

if args:
    usage()
    sys.exit(1)

for o, a in opts:
    if o == "--help":
        usage()
        sys.exit(0)
    elif o == "--verbose":
        verbose = True
    elif o == "--proguard-home":
        proguardHome = a
    elif o == "--php-home":
        phpHome = a
    elif o == "--php-bin-home":
        phpBinHome = a
    elif o == "--ruby-x86-home":
        rubyX86Home = a
    elif o == "--ruby-amd64-home":
        rubyAmd64Home = a
    elif o == "--ruby-devkit-x86-home":
        rubyDevKitX86Home = a
    elif o == "--ruby-devkit-amd64-home":
        rubyDevKitAmd64Home = a
    elif o == "--nodejs-home":
        nodejsHome = a
    elif o == "--gzip-home":
        gzipHome = a
    elif o == "--closure-home":
        closureHome = a
    elif o == "--skip-build":
        skipBuild = True
    elif o == "--skip-installer":
        skipInstaller = True
    elif o == "--filter-languages":
        filterLanguages.append(a)
    elif o == "--filter-compilers":
        filterCompilers.append(a)
    elif o == "--filter-archs":
        filterArchs.append(a)
    elif o == "--filter-confs":
        filterConfs.append(a)
    elif o == "--filter-profiles":
        filterProfiles.append(a)
    elif o == "--rfilter-languages":
        rFilterLanguages.append(a)
    elif o == "--rfilter-compilers":
        rFilterCompilers.append(a)
    elif o == "--rfilter-archs":
        rFilterArchs.append(a)
    elif o == "--rfilter-confs":
        rFilterConfs.append(a)
    elif o == "--rfilter-profiles":
        rFilterProfiles.append(a)
    elif o == "--sign-tool":
        signTool = a
    elif o == "--cert-file":
        certFile = a
    elif o == "--cert-password":
        certPassword = a
    elif o == "--key-file":
        keyFile = a
    elif o == "--winrt":
        winrt = True

basePath = os.path.abspath(os.path.dirname(__file__))
iceBuildHome = os.path.abspath(os.path.join(basePath, "..", ".."))
sourceArchive = os.path.join(iceBuildHome, "Ice-%s.zip" % version)
demoArchive = os.path.join(iceBuildHome, "Ice-%s-demos.zip" % version)

distFiles = os.path.join(iceBuildHome, "distfiles-%s" % version)

iceInstallerFile = os.path.join(distFiles, "src", "windows" , "Ice.aip")
pdbsInstallerFile = os.path.join(distFiles, "src", "windows" , "PDBs.aip")
sdksInstallerFile = os.path.join(distFiles, "src", "windows" , "SDKs.aip")

thirdPartyHome = getThirdpartyHome(version)
if thirdPartyHome is None:
    print("Cannot detect Ice %s ThirdParty installation" % version)
    sys.exit(1)

if not signTool:
    signToolDefaultPath = "c:\\Program Files (x86)\\Microsoft SDKs\Windows\\v7.1A\Bin\\signtool.exe" 
    if os.path.exists(signToolDefaultPath):
        signTool = signToolDefaultPath
else:
    if not os.path.isabs(signTool):
        signTool = os.path.abspath(os.path.join(os.getcwd(), signTool))

if signTool is None:
    print("You need to specify the signtool path using --sign-tool option")
    sys.exit(1)

if not os.path.exists(signTool):
    print("signtool `%s' not found")
    sys.exit(1)


if not certFile:
    if os.path.exists("c:\\release\\authenticode\\zeroc2014.pfx"):
        certFile = "c:\\release\\authenticode\\zeroc2014.pfx"
    elif os.path.exists(os.path.join(os.getcwd(), "..", "..", "release", "authenticode", "zeroc2014.pfx")):
        certFile = os.path.join(os.getcwd(), "..", "..", "release", "authenticode", "zeroc2014.pfx")
else:
    if not os.path.isabs(certFile):
        certFile = os.path.abspath(os.path.join(os.getcwd(), certFile))
        
if certFile is None:
    print("You need to specify the sign certificate using --cert-file option")
    sys.exit(1)

if not os.path.exists(certFile):
    print("Certificate `%s' not found")
    sys.exit(1)

if certPassword is None:
    print("You need to set the sign certificate password using --cert-password option")
    sys.exit(1)

    
if not keyFile:
    if os.path.exists("c:\\release\\strongname\\IceReleaseKey.snk"):
        keyFile = "c:\\release\\strongname\\IceReleaseKey.snk"
    elif os.path.exists(os.path.join(os.getcwd(), "..", "..", "release", "strongname", "IceReleaseKey.snk")):
        keyFile = os.path.join(os.getcwd(), "..", "..", "release", "strongname", "IceReleaseKey.snk")
else:
    if not os.path.isabs(keyFile):
        keyFile = os.path.abspath(os.path.join(os.getcwd(), keyFile))
        
if keyFile is None:
    print("You need to specify the key file to sign assemblies using --key-file option")
    sys.exit(1)

if not os.path.exists(keyFile):
    print("Key file `%s' not found")
    sys.exit(1)

if proguardHome:
    if not os.path.isabs(proguardHome):
        proguardHome = os.path.abspath(os.path.join(os.getcwd(), proguardHome))

    if not os.path.exists(proguardHome):
        #
        # Invalid proguard-home setting
        #
        print("--proguard-home points to nonexistent directory")
        sys.exit(1)

if phpHome:
    if not os.path.isabs(phpHome):
        phpHome = os.path.abspath(os.path.join(os.getcwd(), phpHome))

    if not os.path.exists(phpHome):
        #
        # Invalid proguard-home setting
        #
        print("--php-home points to nonexistent directory")
        sys.exit(1)

if phpBinHome:
    if not os.path.isabs(phpBinHome):
        phpBinHome = os.path.abspath(os.path.join(os.getcwd(), phpBinHome))

    if not os.path.exists(phpBinHome):
        #
        # Invalid proguard-home setting
        #
        print("--php-bin-home points to nonexistent directory")
        sys.exit(1)

if rubyDevKitAmd64Home is None:
    defaultRubyAmd64Home = "C:\\DevKit-mingw64-64-4.7.2"
    if not os.path.exists(defaultRubyAmd64Home):
        print("Ruby DevKit x64 not found in %s" % defaultRubyAmd64Home)
        sys.exit(1)
    rubyDevKitAmd64Home = defaultRubyAmd64Home
elif not os.path.exists(rubyDevKitAmd64Home):
    print("Ruby DevKit x64 not found in %s" % rubyDevKitAmd64Home)
    sys.exit(1)

if rubyDevKitX86Home is None:
    defaultRubyX86Home = "C:\\DevKit-mingw64-32-4.7.3"
    if not os.path.exists(defaultRubyX86Home):
        print("Ruby DevKit x64 not found in %s" % defaultRubyX86Home)
        sys.exit(1)
    rubyDevKitX86Home = defaultRubyX86Home
elif not os.path.exists(rubyDevKitX86Home):
    print("Ruby DevKit x86 not found in %s" % rubyDevKitX86Home)
    sys.exit(1)

if nodejsHome:
    if not os.path.isabs(nodejsHome):
        nodejsHome = os.path.abspath(os.path.join(os.getcwd(), nodejsHome))

    nodejsExe = os.path.join(nodejsHome, "node.exe")
    if not os.path.exists(nodejsExe):
        #
        # Invalid proguard-home setting
        #
        print("node.exe not found in " + nodejsHome)
        sys.exit(1)

if gzipHome:
    if not os.path.isabs(gzipHome):
        gzipHome = os.path.abspath(os.path.join(os.getcwd(), gzipHome))

    gzipExe = os.path.join(gzipHome, "bin", "gzip.exe")
    if not os.path.exists(gzipExe):
        #
        # Invalid proguard-home setting
        #
        print("node.exe not found in " + os.path.join(gzipHome, "bin"))
        sys.exit(1)

if closureHome:
    if not os.path.isabs(closureHome):
        closureHome = os.path.abspath(os.path.join(os.getcwd(), closureHome))

    if not os.path.exists(closureHome):
        #
        # Invalid proguard-home setting
        #
        print("--closure-home points to nonexistent directory")
        sys.exit(1)

if not os.path.exists(sourceArchive):
    print("Couldn't find %s in %s" % (os.path.basename(sourceArchive), os.path.dirname(sourceArchive)))
    sys.exit(1)

if not os.path.exists(demoArchive):
    print("Couldn't find %s in %s" % (os.path.basename(demoArchive), os.path.dirname(demoArchive)))
    sys.exit(1)

    
#
# Windows build configurations by Compiler Arch 
#
global builds
global buildCompilers

if winrt:
    buildCompilers = ["VC110", "VC120"]
    builds = {
    "VC110": {
        "x86": {"release": ["cpp"], "debug": ["cpp"],},
        "amd64": {"release": ["cpp"], "debug": ["cpp"],},
        "arm": {"release": ["cpp"], "debug": ["cpp"],}},
    "VC120": {
        "x86": {"release": ["cpp"], "debug": ["cpp"],},
        "amd64": {"release": ["cpp"], "debug": ["cpp"],},
        "arm": {"release": ["cpp"], "debug": ["cpp"],}}}
else:
    buildCompilers = ["MINGW", "VC100", "VC110", "VC120"]
    builds = {
        "MINGW": {
            "x86": {
                "release": ["cpp", "rb"]},
            "amd64": {
                "release": ["cpp", "rb"]}},
        "VC100": {
            "x86": {
                "release": ["cpp", "py"]},
            "amd64": {
                "release": ["cpp", "py"]}},
        "VC110": {
            "x86": {
                "release": ["cpp", "php", "vsaddin"], 
                "debug": ["cpp"]},
            "amd64": {
                "release": ["cpp"], 
                "debug": ["cpp"]}},
        "VC120": {
            "x86": {
                "release": ["cpp", "java", "js", "cs", "vsaddin"], 
                "debug": ["cpp"]},
            "amd64": {
                "release": ["cpp"], 
                "debug": ["cpp"]}}}
            
if not skipBuild:
    
    for compiler in buildCompilers:

        if filterCompilers and compiler not in filterCompilers:
            continue

        if rFilterCompilers and compiler in rFilterCompilers:
            continue
        
        if compiler not in ["MINGW"]:
            vcvars = getVcVarsAll(compiler)

            if vcvars is None:
                print("Compiler %s not found" % compiler)
                sys.exit(1)
    
        for arch in ["x86", "amd64", "arm"]:
            
            if not arch in builds[compiler]:
                continue
            
            if filterArchs and arch not in filterArchs:
                continue

            if rFilterArchs and arch in rFilterArchs:
                continue

            for conf in ["release", "debug"]:
                
                if not conf in builds[compiler][arch]:
                    continue
        
                if filterConfs and conf not in filterConfs:
                    continue

                if rFilterConfs and conf in rFilterConfs:
                    continue

                buildDir = os.path.join(iceBuildHome, "build-%s-%s-%s" % (arch, compiler, conf))

                if not os.path.exists(buildDir):
                    os.makedirs(buildDir)

                os.chdir(buildDir)

                sourceDir = os.path.join(buildDir, "Ice-%s-src" % version)
                installDir = os.path.join(buildDir, "Ice-%s" % version)
                if not os.path.exists(sourceDir):
                    sys.stdout.write("extracting %s to %s... " % (os.path.basename(sourceArchive), sourceDir))
                    sys.stdout.flush()
                    zipfile.ZipFile(sourceArchive).extractall()
                    if os.path.exists(sourceDir):
                        shutil.rmtree(sourceDir, onerror = _handle_error)
                    shutil.move(installDir, sourceDir)
                    print("ok")

                print ("Build: (%s/%s/%s)" % (compiler,arch,conf))
                for lang in builds[compiler][arch][conf]:

                    if filterLanguages and lang not in filterLanguages:
                        continue

                    if rFilterLanguages and lang in rFilterLanguages:
                        continue

                    env = os.environ.copy()

                    env["THIRDPARTY_HOME"] = thirdPartyHome
                    env["RELEASEPDBS"] = "yes"
                    if conf == "release":
                        env["OPTIMIZE"] = "yes"

                    if lang == "py":
                        pythonHome = getPythonHome(arch)
                        if pythonHome is None:
                            #
                            # Python installation not detected
                            #
                            print("Python 3.4 for arch %s not found" % arch)
                            sys.exit(1)
                        env["PYTHON_HOME"] = pythonHome

                    if lang == "java":
                        javaHome = getJavaHome(arch, "1.7")

                        if javaHome is None:
                            #
                            # Java 1.7 installation not detected
                            #
                            print("Java 1.7 for arch %s not found" % arch)
                            sys.exit(1)
                        env["JAVA_HOME"] = javaHome

                        if proguardHome is None:
                            #
                            # Proguard installation not detected
                            #
                            if not os.path.exists(r"C:\proguard"):
                                print("Proguard not found")
                                sys.exit(1)
                            proguardHome = r"C:\proguard"
                        #
                        # We override CLASSPATH, we just need proguard in classpath to build Ice.
                        #
                        env["CLASSPATH"] = os.path.join(proguardHome, "lib", "proguard.jar")

                    if lang == "php":
                        if phpHome is None:
                            if not os.path.exists(r"C:\php-5.6.1"):
                                print("PHP source distribution not found")
                                sys.exit(1)
                            phpHome = r"C:\php-5.6.1"

                        if phpBinHome is None:
                            if not os.path.exists(r"C:\Program Files (x86)\PHP"):
                                print("PHP bin distribution not found")
                                sys.exit(1)
                            phpBinHome = r"C:\Program Files (x86)\PHP"

                        env["PHP_HOME"] = phpHome
                        env["PHP_BIN_HOME"] = phpBinHome

                    if lang == "js":
                        if nodejsExe is None:
                            nodejsHome = r"C:\Program Files (x86)\nodejs"
                            nodejsExe = os.path.join(nodejsHome, "node.exe")
                            if not os.path.exists(nodejsExe):
                                print("NodeJS not found in default location: `" + nodejsHome + "'")
                                sys.exit(1)

                        if gzipExe is None:
                            gzipHome = r"C:\Program Files (x86)\GnuWin32"
                            gzipExe = os.path.join(gzipHome, "bin", "gzip.exe")
                            if not os.path.exists(gzipExe):
                                print("Gzip executable not found in default location `" + os.path.join(gzipHome, "bin") + "'")
                                sys.exit(1)
                            
                        if closureHome is None:
                            closureHome = r"C:\closure"
                            if not os.path.exists(closureHome):
                                print("Google closure compiler not found in default location `" + closureHome + "'")
                                sys.exit(1)
                            
                        env["NODE"] = nodejsExe
                        env["GZIP_PATH"] = gzipExe
                        env["CLOSURE_PATH"] = closureHome

                    if compiler == "MINGW":
                        if arch =="amd64":
                            rubyDevKitHome = rubyDevKitAmd64Home
                        if arch == "x86":
                            rubyDevKitHome = rubyDevKitX86Home
                            
                    if lang == "rb":
                        if arch == "amd64":
                            if rubyAmd64Home is None:
                                if not os.path.exists(r"C:\Ruby21-x64"):
                                    print("Ruby not found")
                                    sys.exit(1)
                                rubyAmd64Home= r"C:\Ruby21-x64"
                            rubyHome = rubyAmd64Home
                            
                        if arch == "x86":
                            if rubyX86Home is None:
                                if not os.path.exists(r"C:\Ruby21"):
                                    print("Ruby not found")
                                    sys.exit(1)
                                rubyX86Home= r"C:\Ruby21"
                            rubyHome = rubyX86Home

                    if lang == "vsaddin":
                        env["DISABLE_SYSTEM_INSTALL"] = "yes"
                        if compiler == "VC110":
                            env["VS"] = "VS2012"
                        elif compiler == "VC120":
                            env["VS"] = "VS2013"
                            
                    #
                    # Uset the release key to sign .NET assemblies.
                    #
                    if lang == "cs":
                        env["KEYFILE"] = keyFile

                    os.chdir(os.path.join(sourceDir, lang))

                    command = None
                    if compiler != "MINGW":
                        command = "\"%s\" %s  && nmake /f Makefile.mak install prefix=\"%s\"" % \
                                  (vcvars, arch, installDir)
                    
                    if lang not in ["java", "rb"]:
                        rules = "Make.rules.mak"
                        if lang == "cs":
                            rules += ".cs"
                        elif lang == "php":
                            rules += ".php"
                        elif lang == "js":
                            rules += ".js"

                        setMakefileOption(os.path.join(sourceDir, lang, "config", rules), "prefix", installDir)

                    if winrt and lang == "cpp" and compiler in ["VC110", "VC120"]:

                        overwriteFile(os.path.join(sourceDir, "cpp", "src", "Makefile.mak"), winrtMakefile)

                        for profile in ["DESKTOP", "WINRT"]:
                            if filterProfiles and profile not in filterProfiles:
                                continue

                            if rFilterProfiles and profile in rFilterProfiles:
                                continue

                            if profile == "DESKTOP":
                                if arch == "arm":
                                    command = "\"%s\" %s  && nmake /f Makefile.mak install" % (vcvars, "x86")
                                    executeCommand(command, env)
                                else:
                                    command = "\"%s\" %s  && nmake /f Makefile.mak install" % (vcvars, arch)
                                    executeCommand(command, env)
                            elif profile == "WINRT":
                                if arch == "arm":
                                    command = "\"%s\" %s  && nmake /f Makefile.mak install" % (vcvars, "x86_arm")
                                else:
                                    command = "\"%s\" %s  && nmake /f Makefile.mak install" % (vcvars, arch)
                                newEnv = env.copy()
                                newEnv["WINRT"] = "yes"
                                executeCommand(command, newEnv)

                    elif compiler == "MINGW":
                        prefix = installDir
                        if prefix[1] == ":":
                            prefix = "/%s/%s" % (prefix[0], prefix[2:])
                        prefix = re.sub(re.escape("\\"), "/", prefix) 
                        if lang == "cpp":
                            command = "%s\\devkitvars.bat && make install prefix=\"%s\"" % (rubyDevKitHome, prefix)
                            executeCommand(command, env)
                        elif lang == "rb":
                            command = "%s\\bin\\setrbvars.bat && %s\\devkitvars.bat && make install prefix=\"%s\"" % \
                                      (rubyHome, rubyDevKitHome, prefix)
                            executeCommand(command, env)

                    elif lang == "cs":
                        for profile in [".NET", "SILVERLIGHT"]:

                            if filterProfiles and profile not in filterProfiles:
                                continue

                            if rFilterProfiles and profile in rFilterProfiles:
                                continue

                            if profile == ".NET" and compiler == "VC120":
                                executeCommand(command, env)
                            elif profile == "SILVERLIGHT" and compiler == "VC120":
                                newEnv = env.copy()
                                newEnv["SILVERLIGHT"] = "yes"
                                executeCommand(command, newEnv)
                    else:
                        executeCommand(command, env)

#
# Filter files, list of files that must not be included.
#
filterFiles = ["slice35d.dll", "slice35d.pdb", "sliced.lib"]

if not os.path.exists(os.path.join(iceBuildHome, "installer")):
    os.makedirs(os.path.join(iceBuildHome, "installer"))

os.chdir(os.path.join(iceBuildHome, "installer"))

installerDir = os.path.join(iceBuildHome, "installer", "Ice-%s" % version)
pdbinstallerDir = os.path.join(iceBuildHome, "installer/Ice-%s-PDBs" % version)
installerdSrcDir = os.path.join(iceBuildHome, "installer", "Ice-%s-src" % version)
installerDemoDir = os.path.join(iceBuildHome, "installer", "Ice-%s-demos" % version)

if not os.path.exists(installerdSrcDir):
    sys.stdout.write("extracting %s to %s... " % (os.path.basename(sourceArchive), installerdSrcDir))
    sys.stdout.flush()
    zipfile.ZipFile(sourceArchive).extractall()
    shutil.move(installerDir, installerdSrcDir)
    print("ok")


if not os.path.exists(installerDemoDir):
    sys.stdout.write("extracting %s to %s... " % (os.path.basename(demoArchive), installerDemoDir))
    sys.stdout.flush()
    zipfile.ZipFile(demoArchive).extractall()
    print("ok")

for d in [installerDir, pdbinstallerDir]:
    if not os.path.exists(d):
        os.makedirs(d)

if winrt:
    #
    # Remove non winrt demos from demo distribution
    #
    for root, dirnames, filenames in os.walk(installerDemoDir):
        for f in filenames:
            if ((f.endswith(".sln") and f in ["demo-winrt-8.1.sln", "demo-winrt-8.0.sln"]) or
                (os.path.join(root, f).find("winrt\\") != -1)):
                continue
            os.remove(os.path.join(root, f))
        for d in dirnames:
            if ((d == "Ice" and os.path.join(root, d).find("demo\\Ice") != -1) or
                (os.path.join(root, d).find("demo\\Ice\\winrt") != -1) or
                (d == "Glacier2" and os.path.join(root, d).find("demo\\Glacier2") != -1) or
                (os.path.join(root, d).find("demo\\Glacier2\\winrt") != -1) or 
                (d == "demo")):
                continue
            shutil.rmtree(os.path.join(root, d))

    for arch in ["x86", "amd64", "arm"]:
        for compiler in ["VC110", "VC120"]:
            for conf in ["release", "debug"]:

                buildDir = os.path.join(iceBuildHome, "build-%s-%s-%s" % (arch, compiler, conf))
                sourceDir = os.path.join(buildDir, "Ice-%s-src" % version)
                installDir = os.path.join(buildDir, "Ice-%s" % version)

                for root, dirnames, filenames in os.walk(os.path.join(installDir, "SDKs")):
                    for f in filenames:
                        if f in filterFiles:
                            continue
                        targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                        copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)
else:
    #
    # Remove winrt demos from demo distribution
    #
    for root, dirnames, filenames in os.walk(installerDemoDir):
        for f in filenames:
            if f in ["demo-winrt-8.1.sln", "demo-winrt-8.0.sln"]:
                os.remove(os.path.join(root, f))
        for d in dirnames:
            if d == "winrt":
                shutil.rmtree(os.path.join(root, d))

    for arch in ["x86", "amd64"]:
        for compiler in ["VC100", "MINGW", "VC110", "VC120"]:
            for conf in ["release", "debug"]:

                buildDir = os.path.join(iceBuildHome, "build-%s-%s-%s" % (arch, compiler, conf))
                sourceDir = os.path.join(buildDir, "Ice-%s-src" % version)
                installDir = os.path.join(buildDir, "Ice-%s" % version)

                if compiler == "VC120" and arch == "x86" and conf == "release":
                    for d in ["Assemblies", "bin", "config", "include", "lib", "node_modules", "python", "slice", "vsaddin"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                            for f in filenames:
                                if f in filterFiles:
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                #
                                # IceGridGUI.jar in binary distribution should go in the bin directory.
                                #
                                if f == "IceGridGUI.jar":
                                    targetFile = targetFile.replace(os.path.join(installerDir, "lib"), os.path.join(installerDir, "bin"))

                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)

                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                    for f in ["CHANGES.txt", "LICENSE.txt", "ICE_LICENSE.txt", "RELEASE_NOTES.txt"]:
                        copyIfModified(os.path.join(sourceDir, f), os.path.join(installerDir, f), verbose = verbose)

                    #
                    # Copy add-in icon from source dist
                    #
                    copyIfModified(os.path.join(sourceDir, "vsaddin", "icon", "newslice.ico"),
                                   os.path.join(installerDir, "icon", "newslice.ico"), verbose = verbose)

                if compiler == "VC120" and arch == "x86" and conf == "debug":
                    for d in ["bin", "lib"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                            for f in filenames:
                                if f in filterFiles or filterDebugFiles(f):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                if compiler == "VC120" and arch == "amd64" and conf == "release":
                    for d in ["bin", "lib"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d, "x64")):
                            for f in filenames:
                                if f in filterFiles:
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                if compiler == "VC120" and arch == "amd64" and conf == "debug":
                    for d in ["bin", "lib"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d, "x64")):
                            for f in filenames:
                                if f in filterFiles or filterDebugFiles(f):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                #
                # VC110 x86 binaries and libaries
                #
                if compiler == "VC110" and arch == "x86":
                    for d in ["bin", "lib"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                            for f in filenames:
                                if f in filterFiles:
                                    continue
                                if conf == "debug" and filterDebugFiles(f):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                targetFile = os.path.join(os.path.dirname(targetFile), "vc110",
                                                          os.path.basename(targetFile))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)
                    #
                    # VC110 php & vsaddin
                    #
                    if conf == "release":
                        for d in ["php", "vsaddin"]:
                            for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                                for f in filenames:
                                    if f in filterFiles:
                                        continue
                                    targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                    if targetFile.endswith(".pdb"):
                                        targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                    copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)
                #
                # VC110 amd64 binaries and libaries
                #
                if compiler == "VC110" and arch == "amd64":
                    for d in ["bin", "lib"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d, "x64")):
                            for f in filenames:
                                if f in filterFiles:
                                    continue
                                if conf == "debug" and filterDebugFiles(f):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                targetFile = os.path.join(os.path.dirname(os.path.dirname(targetFile)), "vc110", "x64", \
                                                          os.path.basename(targetFile))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)


                #
                # VC100 binaries and libaries
                #
                if compiler == "VC100" and arch == "x86" and conf == "release":
                    for d in ["bin", "python"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                            for f in filenames:
                                if f in filterFiles or (not f.endswith("_vc100.dll") and
                                                        not f.endswith("_vc100.pdb") and
                                                        not f.endswith(".py") and
                                                        not f.endswith(".pyd")):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)


                if compiler == "VC100" and arch == "amd64":
                    for d in ["bin", "python"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d, "x64")):
                            for f in filenames:
                                if f in filterFiles or (not f.endswith("_vc100.dll") and
                                                        not f.endswith("_vc100.pdb") and
                                                        not f.endswith(".py") and
                                                        not f.endswith(".pyd")):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                if targetFile.endswith(".pdb"):
                                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                #
                # MINGW binaries
                #
                if compiler == "MINGW" and arch == "x86" and conf == "release":
                    for d in ["bin", "ruby"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d)):
                            for f in filenames:
                                if f in filterFiles or (not f.endswith(".dll") and
                                                        not f.endswith(".so") and
                                                        not f.endswith(".rb")):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

                if compiler == "MINGW" and arch == "amd64":
                    for d in ["bin", "ruby"]:
                        for root, dirnames, filenames in os.walk(os.path.join(installDir, d, "x64")):
                            for f in filenames:
                                if f in filterFiles or (not f.endswith(".dll") and
                                                        not f.endswith(".so") and
                                                        not f.endswith(".rb")):
                                    continue
                                targetFile = relPath(installDir, installerDir, os.path.join(root, f))
                                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

    #
    # MINGW run-time libraries
    #
    for f in ["libstdc++-6.dll", "libgcc_s_sjlj-1.dll"]:
        copyIfModified(os.path.join(rubyDevKitX86Home, "mingw", "bin", f), os.path.join(installerDir, "bin"), verbose = verbose)
        copyIfModified(os.path.join(rubyDevKitAmd64Home, "mingw", "bin", f), os.path.join(installerDir, "bin", "x64"), verbose = verbose)

    #
    # docs dir
    #
    docsDir = os.path.join(distFiles, "src", "windows", "docs", "main")
    for f in ["README.txt", "SOURCES.txt", "THIRD_PARTY_LICENSE.txt"]:
        copyIfModified(os.path.join(docsDir, f), os.path.join(installerDir, f), verbose = verbose)

    #
    # Copy thirdpary files
    #
    for root, dirnames, filenames in os.walk(thirdPartyHome):
        for f in filenames:
            if f in filterFiles:
                continue
            targetFile = relPath(thirdPartyHome, installerDir, os.path.join(root, f))
            if os.path.splitext(f)[1] in [".exe", ".dll", ".jar", ".pdb"]:
                if targetFile.endswith(".pdb"):
                    targetFile = targetFile.replace(installerDir, pdbinstallerDir)
                copyIfModified(os.path.join(root, f), targetFile, verbose = verbose)

    copyIfModified(os.path.join(thirdPartyHome, "config", "openssl.cnf"),
                   os.path.join(iceBuildHome, "installer", "openssl.cnf"), verbose = verbose)

if not skipInstaller:
    #
    # Build installers with Advanced installer.
    #

    #
    # XML with path variables definitions
    #
    pathVariables = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PathVariables Application="Advanced Installer" Version="10.3">
  <Var Name="ICE_BUILD_HOME" Path="%ICE_BUILD_HOME%" Type="2" ContentType="2"/>
</PathVariables>"""

    advancedInstallerHome = getAdvancedInstallerHome()
    if advancedInstallerHome is None:
        print("Advanced Installer installation not found")
        sys.exit(1)

    advancedInstaller = os.path.join(advancedInstallerHome, "bin", "x86", "AdvancedInstaller.com")

    if not os.path.exists(advancedInstaller):
        print("Advanced Installer executable not found in %s" % advancedInstaller)
        sys.exit(1)

    env = os.environ.copy()    
    env["ICE_BUILD_HOME"] = iceBuildHome

    paths = os.path.join(iceBuildHome, "installer", "paths.xml")
    f = open(os.path.join(iceBuildHome, "installer", "paths.xml"), "w")
    f.write(pathVariables)
    f.close()
    
    tmpCertFile = os.path.join(os.path.dirname(iceInstallerFile), os.path.basename(certFile))
    copy(certFile, tmpCertFile)

    #
    # Load path vars
    #
    command = "\"%s\" /loadpathvars %s" % (advancedInstaller, paths)
    executeCommand(command, env)

    if winrt:
        #
        # Build the Ice WinRT SDKs installer.
        #
        command = "\"%s\" /rebuild %s" % (advancedInstaller, sdksInstallerFile)
        executeCommand(command, env)
        sign(os.path.join(os.path.dirname(iceInstallerFile), "SDKs.msi"), "Ice WinRT SDKs %s" % version)
        shutil.move(os.path.join(os.path.dirname(iceInstallerFile), "SDKs.msi"), \
                                 os.path.join(iceBuildHome, "Ice-WinRT-SDKs-%s.msi" % version))
    else:
        #
        # Build the Ice main installer.
        #    
        command = "\"%s\" /rebuild %s" % (advancedInstaller, iceInstallerFile)
        executeCommand(command, env)
        sign(os.path.join(os.path.dirname(iceInstallerFile), "Ice.msi"), "Ice %s" % version)
        shutil.move(os.path.join(os.path.dirname(iceInstallerFile), "Ice.msi"), \
                                 os.path.join(iceBuildHome, "Ice-%s.msi" % version))

        #
        # Build the Ice PDBs installer.
        #
        command = "\"%s\" /rebuild %s" % (advancedInstaller, pdbsInstallerFile)
        executeCommand(command, env)

        sign(os.path.join(os.path.dirname(iceInstallerFile), "PDBs.msi"), "Ice PDBs %s" % version)
        shutil.move(os.path.join(os.path.dirname(iceInstallerFile), "PDBs.msi"), \
                                 os.path.join(iceBuildHome, "Ice-PDBs-%s.msi" % version))

    remove(tmpCertFile)
