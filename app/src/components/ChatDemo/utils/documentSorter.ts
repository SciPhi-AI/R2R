import { DocumentFilterCriteria, DocumentInfoType } from '../../../types';

export const getFilteredAndSortedDocuments = (
  documents: DocumentInfoType[],
  filterCriteria: DocumentFilterCriteria
) => {
  return [...documents].sort((a, b) => {
    if (filterCriteria.sort === 'title') {
      return filterCriteria.order === 'asc'
        ? a.title.localeCompare(b.title)
        : b.title.localeCompare(a.title);
    } else if (filterCriteria.sort === 'date') {
      return filterCriteria.order === 'asc'
        ? new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime()
        : new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    }
    return 0;
  });
};
