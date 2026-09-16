// Viewer-request function for the /api/* behaviour.
//
// The web app is built with VITE_API_BASE=/api so one CloudFront origin can
// serve both the SPA and the API, but the API itself has no /api prefix.
// Strip it here so the request reaches the load balancer as the API expects
// (/api/episodes -> /episodes). The ALB health check calls /health directly
// and never passes through this function.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri === "/api") {
    request.uri = "/";
  } else if (uri.indexOf("/api/") === 0) {
    request.uri = uri.substring(4);
  }
  return request;
}
