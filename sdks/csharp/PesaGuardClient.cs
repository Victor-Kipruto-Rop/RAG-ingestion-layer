using System.Net;
using System.Net.Http.Headers;

namespace PesaGuard;

/// <summary>Minimal .NET 8 server-side HTTP client starter.</summary>
public sealed class PesaGuardClient
{
    private readonly HttpClient _http;
    private readonly string _baseUrl;

    public PesaGuardClient(string? apiKey = null, string environment = "sandbox", HttpClient? httpClient = null)
    {
        apiKey ??= Environment.GetEnvironmentVariable("PESAGUARD_API_KEY");
        var (expected, prefix) = environment switch
        {
            "sandbox" => ("https://sandbox-api.pesaguard.co.ke", "pg_sandbox_"),
            "production" => ("https://api.pesaguard.co.ke", "pg_live_"),
            _ => throw new ArgumentException("environment must be sandbox or production")
        };
        if (string.IsNullOrWhiteSpace(apiKey) || !apiKey.StartsWith(prefix, StringComparison.Ordinal))
            throw new ArgumentException($"Selected environment requires a {prefix} API key");
        _baseUrl = Environment.GetEnvironmentVariable("PESAGUARD_BASE_URL")?.TrimEnd('/') ?? expected;
        if (!Uri.TryCreate(_baseUrl, UriKind.Absolute, out var uri) || uri.Host != new Uri(expected).Host)
            throw new ArgumentException("Base URL does not match selected environment");
        _http = httpClient ?? new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
        _http.DefaultRequestHeaders.Add("X-API-Key", apiKey);
        _http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public async Task<string> SearchRegistryAsync(string query, CancellationToken cancellationToken = default)
    {
        var uri = $"{_baseUrl}/api/v1/registry/search?q={Uri.EscapeDataString(query)}";
        using var response = await _http.GetAsync(uri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"PesaGuard API returned HTTP {(int)response.StatusCode}");
        return await response.Content.ReadAsStringAsync(cancellationToken);
    }
}
