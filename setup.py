from setuptools import setup, find_packages

setup(
    name="prototype_ingos",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "redis>=5.0.0",
        "pydub>=0.25.1",
        "grpcio>=1.62",
        "grpcio-tools>=1.62",
        "python-dotenv>=1.0",
        "PyYAML>=6.0",
        "requests",
        "ffmpeg-python>=0.2.0",  # For OPUS encoding
    ],
    python_requires=">=3.10",
) 