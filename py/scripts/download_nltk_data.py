import ssl

import nltk


def download_nltk_data():
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    nltk.download("wordnet", quiet=True)


if __name__ == "__main__":
    download_nltk_data()
