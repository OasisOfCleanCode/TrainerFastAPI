from setuptools import setup, find_packages
from version import get_app_version


def parse_requirements(filename):
    with open(filename, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


install_requires = parse_requirements("requirements.in")

setup(
    name="TrainerAPI",
    version=get_app_version(),
    description="Trainer API Application — part of the Oasis of Clean Code project",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="dmitrij-el",
    author_email="",
    url="https://github.com/OasisOfCleanCode/TrainerAPI",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
        "Operating System :: OS Independent"
    ],
    python_requires=">=3.12",
    project_urls={
        "Source": "https://github.com/OasisOfCleanCode/TrainerAPI",
        "Privacy Policy": "https://raw.githubusercontent.com/OasisOfCleanCode/TrainerAPI/dev/templates/privacy_policy_oasis.html",
    }
)
