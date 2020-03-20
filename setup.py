from setuptools import setup

requirements = "serial", "requests", "black", "pylint"
setup(
    name="Igate-n",
    version="0.0a",
    packages=["tests", "IGaten"],
    url="https://github.com/9V1KG/Igate-n",
    license="Please check with author",
    author="9V1KG",
    author_email="",
    install_requires=requirements,
    description="APRS for Yaesu Radio",
)
