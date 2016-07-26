#!/bin/sh

# Creates the deployment package (.zip file) to be uploaded to AWS Lambda

HOME_DIR="/Users/mattklein"
BASE_DIR="$HOME_DIR/code/misc/pers_finance_2016"
BUILD_DIR="$BASE_DIR/build"
VIRTUALENV_DIR="$HOME_DIR/work/siphonenv"
THIRDPARTY_DIR="$BASE_DIR/thirdparty"
TARGET_ZIP_FILE="$BUILD_DIR/lambda_deployment.zip"

rm -rf "$BUILD_DIR"
mkdir "$BUILD_DIR"

type1() {
    # The Python code we'll import (either a directory or a single file) is contained inside a directory in site-packages (typically the directory has the .egg suffix)
    echo "   $2"
    cd "$VIRTUALENV_DIR/$1/python2.7/site-packages/$2"
    zip -r "$TARGET_ZIP_FILE" $3 > /dev/null
}
type2() {
    # The Python code we'll import (either a directory or a single file) sits directly in site-packages
    echo "   $2"
    cd "$VIRTUALENV_DIR/$1/python2.7/site-packages"
    zip -r "$TARGET_ZIP_FILE" $2 > /dev/null
}
type3() {
    # The Python code we'll import (either a directory or a single file) is contained in an .egg FILE (not a directory) -- we need to unzip that .egg file
    echo "   $2"
    cd "$VIRTUALENV_DIR/$1/python2.7/site-packages"
    rm -rf /tmp/$2
    mkdir /tmp/$2
    cp $2 /tmp/$2
    cd /tmp/$2
    unzip $2 > /dev/null
    zip -r "$TARGET_ZIP_FILE" $3 > /dev/null
}

add_packages_from_virtualenv() {
    echo "Adding packages from virtualenv"
    type1 lib boto-2.38.0-py2.7.egg boto
    type2 lib jinja2
    type2 lib markupsafe
    # It seems to be working to grab SQLAchemy's .egg as built on MacOS and use it on Lambda's Linux.
    # If it turns out not to be working, the solution is to build SQLAlchemy's .egg (via setup.py install)
    # on an Amazon Linux machine, then put that .egg into the .zip for Lambda.
    type1 lib SQLAlchemy-0.9.2-py2.7-macosx-10.10-intel.egg sqlalchemy
}

add_thirdparty_packages() {
    echo "Adding thirdparty packages"

    echo "   awslambda-psycopg2"
    cd "$THIRDPARTY_DIR/awslambda-psycopg2"
    zip -r "$TARGET_ZIP_FILE" psycopg2 > /dev/null
}

add_codebase() {
    echo "Adding codebase"

    cd "$BASE_DIR/src"
    find persfin | zip "$TARGET_ZIP_FILE" -@ > /dev/null

    cd "$BASE_DIR/src"
    find credentials | zip "$TARGET_ZIP_FILE" -@ > /dev/null

    # Lambda needs the Lambda function's module to be in the root of the .zip file -- it doesn't
    # work to specify the path to it as a Python module
    # This directory contains all of the top-level Lambda functions; so we'll put everything here
    # into the root of the .zip file
    cd "$BASE_DIR/src/persfin/awslambda"
    zip "$TARGET_ZIP_FILE" * > /dev/null
}

add_packages_from_virtualenv
add_thirdparty_packages
add_codebase
exit 0
