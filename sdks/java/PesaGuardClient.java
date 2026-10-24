import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/** Minimal Java 17+ server-side client starter. */
public final class PesaGuardClient {
    private final String apiKey;
    private final String baseUrl;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5))
        .followRedirects(HttpClient.Redirect.NEVER).build();

    public PesaGuardClient(String apiKey, String environment) {
        String env = environment == null || environment.isBlank() ? "sandbox" : environment;
        String expected, prefix;
        if (env.equals("sandbox")) { expected = "https://sandbox-api.pesaguard.co.ke"; prefix = "pg_sandbox_"; }
        else if (env.equals("production")) { expected = "https://api.pesaguard.co.ke"; prefix = "pg_live_"; }
        else throw new IllegalArgumentException("environment must be sandbox or production");
        if (apiKey == null || !apiKey.startsWith(prefix)) throw new IllegalArgumentException("Selected environment requires " + prefix + " API key");
        String override = System.getenv("PESAGUARD_BASE_URL");
        String candidate = override == null || override.isBlank() ? expected : override.replaceAll("/+$", "");
        if (!URI.create(candidate).getHost().equalsIgnoreCase(URI.create(expected).getHost())) throw new IllegalArgumentException("Base URL does not match selected environment");
        this.apiKey = apiKey; this.baseUrl = candidate;
    }

    public HttpResponse<String> searchRegistry(String query) throws Exception {
        String url = baseUrl + "/api/v1/registry/search?q=" + URLEncoder.encode(query, StandardCharsets.UTF_8);
        HttpRequest request = HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10))
            .header("X-API-Key", apiKey).header("Accept", "application/json").GET().build();
        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) throw new IllegalStateException("PesaGuard API returned HTTP " + response.statusCode());
        return response;
    }
}
