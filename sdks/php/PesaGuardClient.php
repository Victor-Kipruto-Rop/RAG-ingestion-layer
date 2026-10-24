<?php
declare(strict_types=1);

/** PesaGuard server-side HTTP SDK starter. Requires PHP 8.1 and ext-curl. */
final class PesaGuardClient
{
    private const BASE_URLS = [
        'sandbox' => 'https://sandbox-api.pesaguard.co.ke',
        'production' => 'https://api.pesaguard.co.ke',
    ];
    private string $baseUrl;

    public function __construct(private readonly string $apiKey, private readonly string $environment = 'sandbox', private readonly int $timeout = 10)
    {
        if (!isset(self::BASE_URLS[$environment])) throw new InvalidArgumentException('environment must be sandbox or production');
        $prefix = $environment === 'sandbox' ? 'pg_sandbox_' : 'pg_live_';
        if (!str_starts_with($apiKey, $prefix)) throw new InvalidArgumentException("Selected environment requires {$prefix} API key");
        $this->baseUrl = rtrim(getenv('PESAGUARD_BASE_URL') ?: self::BASE_URLS[$environment], '/');
        if (parse_url($this->baseUrl, PHP_URL_HOST) !== parse_url(self::BASE_URLS[$environment], PHP_URL_HOST)) throw new InvalidArgumentException('Base URL does not match selected environment');
    }

    public function request(string $path, array $query = []): array
    {
        $url = $this->baseUrl . '/' . ltrim($path, '/');
        if ($query) $url .= '?' . http_build_query($query);
        $curl = curl_init($url);
        curl_setopt_array($curl, [
            CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_CONNECTTIMEOUT => $this->timeout, CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_HTTPHEADER => ['X-API-Key: ' . $this->apiKey, 'Accept: application/json'],
        ]);
        $body = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        if ($body === false) { curl_close($curl); throw new RuntimeException('PesaGuard request failed'); }
        curl_close($curl);
        if ($status < 200 || $status >= 300) throw new RuntimeException("PesaGuard API returned HTTP {$status}");
        return $body === '' ? [] : (array) json_decode($body, true, 512, JSON_THROW_ON_ERROR);
    }

    public function searchRegistry(string $query): array { return $this->request('/api/v1/registry/search', ['q' => $query]); }
}
