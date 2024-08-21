import nltk


def download_nltk_data():
    nltk.download("wordnet", quiet=True)


if __name__ == "__main__":
    download_nltk_data()
