import React, { FC, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { VectorSearchResult, KGSearchResult } from '@/types';

const VectorSearchResultItem: FC<{
    source: VectorSearchResult;
    index: number;
    onOpenPdfPreview: (documentId: string, page?: number) => void;
  }> = ({ source, index, onOpenPdfPreview }) => {
    const { document_id, score, metadata, text } = source;
  
    return (
      <div
        className="p-4 mb-2 flex items-center"
        style={{ width: '100%',  }}
      >
        <div className="flex-grow mr-4">
          <div className="flex items-center mb-1">
            <h3 className="text-sm font-medium mr-2 overflow-hidden overflow-ellipsis">
              [{index}] {metadata.title}
            </h3>
            <div className="flex-grow"></div>
            <span className="text-xs ml-2 whitespace-nowrap text-zinc-500">
              Similarity Score: {source.score.toFixed(3)}
            </span>
          </div>
  
          <p className="text-xs text-wrap" style={{ whiteSpace: 'normal', wordWrap: 'break-word', overflowWrap: 'break-word' }}>{text}</p>
          <p className="text-xs pt-4 text-zinc-500">
            Document ID: {source.document_id}
            <br />
            Fragment ID: {source.fragment_id}
          </p>
        </div>
      </div>
    );
  };
  

const KGSearchResultItem: FC<{ entity: any, index: number }> = ({ entity, index }) => {
  console.log('entity = ', entity);
  return (
      <div
        className="p-4 mb-2 flex items-center"
        style={{ width: '100%',  }}
      >
        <div className="flex-grow mr-4">
          <div className="flex items-center mb-1">
            <h3 className="text-sm font-medium mr-2 overflow-hidden overflow-ellipsis">
              [{index}] {entity.content.name}
            </h3>
            <div className="flex-grow"></div>
            <span className="text-xs ml-2 whitespace-nowrap text-zinc-500">
              Similarity Score: 0
            </span>
          </div>
  
          <p className="text-xs text-wrap" style={{ whiteSpace: 'normal', wordWrap: 'break-word', overflowWrap: 'break-word' }}>{entity.content.description}</p>
          <p className="text-xs pt-4 text-zinc-500">
            Document ID: {entity.document_id}
            <br />
            Fragment ID: {entity.fragment_id}
          </p>
        </div>
      </div>
  );
};

class KGSearchResult {
  
}

interface SearchResultsProps {
  vectorSearchResults: VectorSearchResult[];
  entities: KGSearchResult[];
  communities: KGSearchResult[];
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  vectorSearchResults,
  entities,
  communities,
}) => {

  console.log('entities = ', entities);
  console.log('communities = ', communities);

  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false);
  const handleClosePdfPreview = () => {
    setPdfPreviewOpen(false);
  };
  const [initialPage, setInitialPage] = useState<number>(1);
  const [pdfPreviewDocumentId, setPdfPreviewDocumentId] = useState<
    string | null
  >(null);

  const openPdfPreview = (documentId: string, page?: number) => {
    setPdfPreviewDocumentId(documentId);
    if (page && page > 0) {
      setInitialPage(page);
    } else {
      setInitialPage(1);
    }
    setPdfPreviewOpen(true);

    setPdfPreviewOpen(true);
  };

return (
    <div className="flex justify-center text-zinc-200 rounded-lg">
      <Tabs defaultValue="vectorSearch" className="text-zinc-900 w-full max-w-2xl">
        <TabsList>
          <TabsTrigger value="vectorSearch" >Vector Search</TabsTrigger>
          <TabsTrigger value="kgEntities" >KG Entities</TabsTrigger>
          <TabsTrigger value="kgCommunities" >KG Communities</TabsTrigger>
        </TabsList>
        <TabsContent value="vectorSearch" >
          <Carousel >
            <CarouselContent>
              {vectorSearchResults.map((source, index) => (
                <CarouselItem key={index}>
                  <div className="p-4">
                    <Card className="h-96 overflow-y-auto">
                      <CardContent>
                        <div className="mt-4" />
                        <VectorSearchResultItem
                          source={source}
                          index={index+1}
                          onOpenPdfPreview={openPdfPreview}
                        />
                      </CardContent>
                    </Card>
                  </div>
                </CarouselItem>
              ))}
            </CarouselContent>
            <CarouselPrevious />
            <CarouselNext />
          </Carousel>
        </TabsContent>

       
        <TabsContent value="kgEntities" >
          {/* {kgSearchResults.map((result, index) => (
            <KGSearchResultItem key={index} entity={result} />
          ))} */}
          <Carousel >
            <CarouselContent>
              {entities.map((result, index) => (
                <CarouselItem key={index}>
                  <div className="p-4">
                    <Card className="h-96 overflow-y-auto">
                      <CardContent>
                        <div className="mt-4" />
                        <KGSearchResultItem key={index} entity={result} index={index+1} />
                      </CardContent>
                    </Card>
                  </div>
                </CarouselItem>
              ))}
            </CarouselContent>
            <CarouselPrevious />
            <CarouselNext />
          </Carousel>
        </TabsContent>
  
        <TabsContent value="kgCommunities" >
          {/* {kgSearchResults.map((result, index) => (
            <KGSearchResultItem key={index} entity={result} />
          ))} */}
          <Carousel>
            <CarouselContent>
              {communities.map((result, index) => (
                <CarouselItem key={index}>
                  <div className="p-4">
                    <Card className="h-96 overflow-y-auto">
                      <CardContent>
                        <div className="mt-4" />
                        <KGSearchResultItem key={index} entity={result} index={index+1} />
                      </CardContent>
                    </Card>
                  </div>
                </CarouselItem>
              ))}
            </CarouselContent>
            <CarouselPrevious />
            <CarouselNext />
          </Carousel>
        </TabsContent>
      </Tabs>
      {/* <PdfPreviewDialog
        documentId={pdfPreviewDocumentId || ''}
        open={pdfPreviewOpen}
        onClose={handleClosePdfPreview}
        initialPage={initialPage}
      /> */}
    </div>
  );
};
