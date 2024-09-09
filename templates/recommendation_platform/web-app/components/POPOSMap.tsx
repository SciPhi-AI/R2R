import React, { useState, useEffect } from "react";
import {
  GoogleMap,
  useJsApiLoader,
  Marker,
  InfoWindow,
} from "@react-google-maps/api";

interface POPOS {
  NAME: string;
  POPOS_ADDRESS: string;
  HOURS: string;
  latitude: string;
  longitude: string;
  [key: string]: string;
}

interface SearchResult {
  address: string;
  latitude: number;
  longitude: number;
  description: string;
}

interface POPOSMapProps {
  poposData: POPOS[];
  searchResults: SearchResult[];
}

const mapContainerStyle = {
  width: "100%",
  height: "400px",
  borderRadius: "0.5rem",
};

const center = {
  lat: 37.79,
  lng: -122.4,
};

const POPOSMap: React.FC<POPOSMapProps> = ({ poposData, searchResults }) => {
  const { isLoaded } = useJsApiLoader({
    id: "google-map-script",
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
  });

  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(
    null,
  );
  const [showOriginalMarkers, setShowOriginalMarkers] = useState(true);

  useEffect(() => {
    setShowOriginalMarkers(searchResults.length === 0);
  }, [searchResults]);

  if (!isLoaded) return <div>Loading...</div>;

  return (
    <div style={{ display: "flex", justifyContent: "center" }}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        center={center}
        zoom={15}
      >
        {showOriginalMarkers &&
          poposData.map((popos, index) => (
            <Marker
              key={`popos-${index}`}
              position={{
                lat: parseFloat(popos.latitude),
                lng: parseFloat(popos.longitude),
              }}
              icon={{
                path: google.maps.SymbolPath.CIRCLE,
                fillColor: "#C5D86D",
                fillOpacity: 1,
                strokeWeight: 0,
                scale: 8,
              }}
            />
          ))}

        {!showOriginalMarkers &&
          searchResults.map((result, index) => (
            <Marker
              key={`search-${index}`}
              position={{
                lat: result.latitude,
                lng: result.longitude,
              }}
              onClick={() => setSelectedResult(result)}
              icon={{
                path: google.maps.SymbolPath.CIRCLE,
                fillColor: "#FF0000",
                fillOpacity: 1,
                strokeWeight: 0,
                scale: 8,
              }}
            />
          ))}

        {selectedResult && (
          <InfoWindow
            position={{
              lat: selectedResult.latitude,
              lng: selectedResult.longitude,
            }}
            onCloseClick={() => setSelectedResult(null)}
          >
            <div>
              <h2>{selectedResult.address}</h2>
              <p>{selectedResult.description}</p>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </div>
  );
};

export default POPOSMap;
