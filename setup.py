from setuptools import setup, find_packages
from version import get_app_version


def parse_requirements(filename):
    with open(filename, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


install_requires = parse_requirements("requirements.in")

setup(
    name="web_app",
    version=get_app_version(),
    description="Trainer API Application. Oasis of Clear Code",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="dmitrij-el",
    author_email="",
    url="",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    license="MIT",
    classifiers=[],
    python_requires=">=3.12",
)
