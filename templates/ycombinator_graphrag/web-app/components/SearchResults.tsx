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
import { VectorSearchResult, KGLocalSearchResult } from '@/types';

const VectorSearchResultItem: FC<{
    source: VectorSearchResult;
    index: number;
    onOpenPdfPreview: (documentId: string, page?: number) => void;
  }> = ({ source, index, onOpenPdfPreview }) => {
    const { document_id, score, metadata, text } = source;
  
    return (
      <div
        className="bg-zinc-700 p-4 rounded-lg mb-2 flex items-center"
        style={{ width: '100%' }}
      >
        <div className="flex-grow mr-4">
          <div className="flex items-center mb-1">
            <h3 className="text-sm font-medium text-zinc-300 mr-2 overflow-hidden overflow-ellipsis">
              [{index}] {metadata.title}
            </h3>
            <div className="flex-grow"></div>
            <span className="text-xs text-zinc-500 ml-2 whitespace-nowrap">
              Similarity Score: {source.score.toFixed(3)}
            </span>
          </div>
  
          <p className="text-xs text-zinc-400 text-wrap" style={{ whiteSpace: 'normal', wordWrap: 'break-word', overflowWrap: 'break-word' }}>{text}</p>
          <p className="text-xs text-zinc-500 pt-4">
            Document ID: {source.document_id}
            <br />
            Fragment ID: {source.fragment_id}
          </p>
        </div>
      </div>
    );
  };
  

const KGEntityResult: FC<{ entity: any }> = ({ entity }) => {
  return (
    <div className="bg-zinc-700 p-4 rounded-lg mb-2">
      <h3 className="text-sm font-medium text-zinc-300 mb-1">{entity.name}</h3>
      <p className="text-xs text-zinc-400">{entity.description}</p>
    </div>
  );
};

interface SearchResultsProps {
  vectorSearchResults: VectorSearchResult[];
  kgLocalSearchResult: KGLocalSearchResult | null;
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  vectorSearchResults,
  kgLocalSearchResult,
}) => {
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

  console.log('kgLocalSearchResult.entities = ', kgLocalSearchResult.entities)
  console.log('kgLocalSearchResult.communities = ', kgLocalSearchResult.communities)

return (
    <div className="flex justify-center text-zinc-200 bg-zinc-200 rounded-lg">
      <Tabs defaultValue="vectorSearch" className="text-zinc-900 w-full max-w-2xl">
        <TabsList>
          <TabsTrigger value="vectorSearch" >Vector Search</TabsTrigger>
          {kgLocalSearchResult && kgLocalSearchResult?.entities && (
            <TabsTrigger value="kgEntities">KG Entities</TabsTrigger>
          )}
          {kgLocalSearchResult && kgLocalSearchResult?.communities && (
            <TabsTrigger value="kgCommunities">KG Communities</TabsTrigger>
          )}

        </TabsList>
        <TabsContent value="vectorSearch" >
          <Carousel>
            <CarouselContent>
              {vectorSearchResults.map((source, index) => (
                <CarouselItem key={index}>
                  <div className="p-4">
                    <Card className="h-96 overflow-y-auto bg-zinc-900">
                      <CardContent>
                        <div className="mt-4" />
                        <VectorSearchResultItem
                          source={source}
                          index={index}
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
        {kgLocalSearchResult && kgLocalSearchResult?.entities && (
          <TabsContent value="kgEntities">
            <Carousel>
              <CarouselContent>
                {Object.entries(kgLocalSearchResult.entities).map(
                  ([_, entity]) => (
                    <CarouselItem key={entity.name}>
                      <div className="p-4">
                        <Card className="h-96 overflow-y-auto bg-zinc-900">
                          <CardContent>
                            <div className="mt-4" />
                            <KGEntityResult entity={entity} />
                          </CardContent>
                        </Card>
                      </div>
                    </CarouselItem>
                  )
                )}
              </CarouselContent>
              <CarouselPrevious />
              <CarouselNext />
            </Carousel>
          </TabsContent>
        )}
        {kgLocalSearchResult && kgLocalSearchResult?.communities && (
          <TabsContent value="kgCommunities">
            <Carousel>
              <CarouselContent>
                {Object.entries(kgLocalSearchResult.communities).map(
                  ([_, community]) => (
                    <CarouselItem key={community.title}>
                      <div className="p-4">
                        <Card className="h-96 overflow-y-auto bg-zinc-900">
                          <CardContent>
                            <div className="mt-4" />
                            <KGEntityResult entity={community.summary} />
                          </CardContent>
                        </Card>
                      </div>
                    </CarouselItem>
                  )
                )}
              </CarouselContent>
              <CarouselPrevious />
              <CarouselNext />
            </Carousel>
          </TabsContent>
        )}

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
