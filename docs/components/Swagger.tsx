// @ts-nocheck

// import SwaggerUI from "swagger-ui-react";
import dynamic from 'next/dynamic';

const SwaggerUI = dynamic<{
  spec: any;
}>(import('swagger-ui-react'), { ssr: false });

const App = () => (
  <SwaggerUI
    url="/swagger.json"
  />
);

export default App;