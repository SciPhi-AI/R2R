import nltk
from setuptools import setup

def download_nltk_data():
    nltk.download('wordnet', quiet=True)

setup(
    name='r2r',
    version='0.3.0',
    setup_requires=['nltk'],
    cmdclass={
        'install': lambda _: download_nltk_data(),
    },
)