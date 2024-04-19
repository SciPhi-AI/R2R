// pages/_app.tsx

import type { AppProps } from "next/app";
import "swagger-ui-react/swagger-ui.css";
import '../public/redoc.css';

function MyApp({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}

export default MyApp;