export const environment = {
  production: false,
  // APISIX Ingress Gateway (:9080) routes /reports/* to P2 (:8081) and /* to P1 (:8000)
  apiUrl: 'http://localhost:9080',
  reportsApiUrl: 'http://localhost:9080',
  keycloak: {
    url: 'http://localhost:8080',
    realm: 'doc-intelligence',
    clientId: 'doc-intelligence-ui',
  },
};
