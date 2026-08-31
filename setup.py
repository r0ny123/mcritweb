from setuptools import setup

setup(
    name="mcritweb",
    version="1.4.8",
    packages=["mcritweb"],
    # not a preference, an inherited constraint: every mcrit release this can
    # install requires >=3.11, and 1.5.3 is the first to declare it. Undeclared,
    # an install on 3.10 fails with a resolver error about mcrit that names
    # neither Python nor the version the reader needs.
    python_requires=">=3.11",
    include_package_data=True,
    install_requires=[
        "flask>=3.0",
        "werkzeug>=3.0",
        "flask-dropzone",
        "Pillow",
        "numpy",
        "scipy", 
        "fastcluster",
        "networkx",
        "mcrit>=1.5.3",
        "levenshtein",
        "markdown"
    ],
)
