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
  const { document_id, metadata, text, score, fragment_id } = source;

  return (
    <div className="p-4 mb-2 flex items-center w-full">
      <div className="flex-grow mr-4">
        <div className="flex items-center mb-1">
          <h3 className="text-sm font-medium mr-2 overflow-hidden overflow-ellipsis">
            [{index}] {metadata.title}
          </h3>
          <div className="flex-grow"></div>
          <span className="text-xs ml-2 whitespace-nowrap text-zinc-500">
            Similarity Score: {score.toFixed(3)}
          </span>
        </div>

        <p className="text-xs text-wrap break-words">{text}</p>
        <p className="text-xs pt-4 text-zinc-500">
          Document ID: {document_id}
          <br />
          Fragment ID: {fragment_id}
        </p>
      </div>
    </div>
  );
};

// const KGSearchResultItem: FC<{ entity: KGSearchResult; index: number }> = ({
//   entity,
//   index,
// }) => {
//   const { content } = entity;

//   return (
//     <div className="p-4 mb-2 flex items-center w-full">
//       <div className="flex-grow mr-4">
//         <div className="flex items-center mb-1">
//           <h3 className="text-sm font-medium mr-2 overflow-hidden overflow-ellipsis">
//             [{index}] {content.name}
//           </h3>
//         </div>

//         <p className="text-xs text-wrap break-words">{content.description}</p>
//       </div>
//     </div>
//   );
// };

const KGSearchResultItem: FC<{ entity: KGSearchResult; index: number }> = ({
  entity,
  index,
}) => {
  const { content, metadata } = entity;
  const findings = metadata?.findings;

  return (
    <div className="p-4 mb-2 flex flex-col w-full">
      <div className="flex-grow">
        {/* Title */}
        <div className="flex items-center mb-2">
          <h3 className="text-sm font-medium overflow-hidden overflow-ellipsis">
            [{index}] {content.name}
          </h3>
        </div>
        <h4 className="text-sm font-semibold mb-1">Summary:</h4>

        {/* Description */}
        {content.description && (
          <p className="text-xs break-words mb-2">{content.description}</p>
        )}

        {/* Findings */}
        {findings && findings.length > 0 && (
          <div>
            <h4 className="text-sm font-semibold mb-1">Findings:</h4>
            <ul className="list-disc list-inside text-xs pl-4">
              {findings.map((finding: string, idx: number) => (
                <li key={idx} className="mb-1">
                  {finding}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

interface SearchResultsProps {
  vectorSearchResults: VectorSearchResult[];
  entities: KGSearchResult[];
  communities: KGSearchResult[];
}

const ResultCarousel: FC<{
  items: any[];
  ItemComponent: FC<any>;
  offset: number;
}> = ({ items, ItemComponent, offset = 0 }) => (
  <Carousel>
    <CarouselContent>
      {items.map((item, index) => (
        <CarouselItem key={index}>
          <Card className="h-48 overflow-y-auto">
            <CardContent>
              <ItemComponent {...item} index={index + offset + 1} />
            </CardContent>
          </Card>
        </CarouselItem>
      ))}
    </CarouselContent>
    <CarouselPrevious />
    <CarouselNext />
  </Carousel>
);

export const SearchResults: React.FC<SearchResultsProps> = ({
  vectorSearchResults,
  entities,
  communities,
}) => {
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false);
  const [initialPage, setInitialPage] = useState<number>(1);
  const [pdfPreviewDocumentId, setPdfPreviewDocumentId] = useState<
    string | null
  >(null);

  const openPdfPreview = (documentId: string, page?: number) => {
    setPdfPreviewDocumentId(documentId);
    setInitialPage(page && page > 0 ? page : 1);
    setPdfPreviewOpen(true);
  };

  return (
    <div className="flex justify-center text-zinc-200 rounded-lg">
      <Tabs
        defaultValue="kgCommunities"
        className="text-zinc-900 w-full max-w-2xl"
      >
        <TabsList>
          <TabsTrigger value="vectorSearch">Vector Search</TabsTrigger>
          <TabsTrigger value="kgEntities">KG Entities</TabsTrigger>
          <TabsTrigger value="kgCommunities">KG Communities</TabsTrigger>
        </TabsList>
        <TabsContent value="vectorSearch">
          <ResultCarousel
            items={vectorSearchResults.map((source) => ({
              source,
              onOpenPdfPreview: openPdfPreview,
            }))}
            ItemComponent={VectorSearchResultItem}
            offset={0}
          />
        </TabsContent>
        <TabsContent value="kgEntities">
          <ResultCarousel
            items={entities.map((entity) => ({ entity }))}
            ItemComponent={KGSearchResultItem}
            offset={vectorSearchResults.length}
          />
        </TabsContent>
        <TabsContent value="kgCommunities">
          <ResultCarousel
            items={communities.map((entity) => ({ entity }))}
            ItemComponent={KGSearchResultItem}
            offset={vectorSearchResults.length + entities.length}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};
