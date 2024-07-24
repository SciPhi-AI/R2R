


# def select_files_for_upload(folder, force=False, data_len=10):
#     # check if folder doesn't exist
#     if not os.path.exists(folder) or force:
#         # remove dir
#         if os.path.exists(folder):
#             os.system(f"rm -rf {folder}")

#         os.makedirs(folder, exist_ok=True)
#         data = load_dataset('json', data_files = '/Users/shreyas/code/parsing/R2R/r2r/evals/corpus.json')
#         for i in range(min(len(data['train']), data_len)):
#             with open(f"{folder}/{i}.txt", "w") as f:
#                 keys = ['title', 'author', 'source', 'published_at', 'category', 'url', 'body']
#                 for key in keys:
#                     if key in data['train'][i] and data['train'][i][key] is not None:
#                         f.write(f"{key.capitalize()}: ")
#                         f.write(str(data['train'][i][key]))
#                         f.write("\n\n")



# https://raw.githubusercontent.com/lgresearch/QASA/main/data/testset_answerable_1554_v1.1.json

