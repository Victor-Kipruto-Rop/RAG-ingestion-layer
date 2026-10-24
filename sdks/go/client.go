// Package pesaguard is a small server-side HTTP client starter.
package pesaguard

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type Client struct { APIKey, BaseURL string; HTTP *http.Client }

func New(apiKey, environment string) (*Client, error) {
	if apiKey == "" { apiKey = os.Getenv("PESAGUARD_API_KEY") }
	if environment == "" { environment = os.Getenv("PESAGUARD_ENV"); if environment == "" { environment = "sandbox" } }
	base, prefix := "", ""
	switch environment { case "sandbox": base, prefix = "https://sandbox-api.pesaguard.co.ke", "pg_sandbox_"; case "production": base, prefix = "https://api.pesaguard.co.ke", "pg_live_"; default: return nil, fmt.Errorf("environment must be sandbox or production") }
	if !strings.HasPrefix(apiKey, prefix) { return nil, fmt.Errorf("selected environment requires a %s API key", prefix) }
	if override := os.Getenv("PESAGUARD_BASE_URL"); override != "" { u, err := url.Parse(override); if err != nil { return nil, err }; expected, _ := url.Parse(base); if u.Hostname() != expected.Hostname() { return nil, fmt.Errorf("base URL does not match selected environment") }; base = strings.TrimRight(override, "/") }
	return &Client{APIKey: apiKey, BaseURL: base, HTTP: &http.Client{Timeout: 10*time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}, nil
}

func (c *Client) SearchRegistry(ctx context.Context, query string) (map[string]any, error) {
	u := c.BaseURL + "/api/v1/registry/search?q=" + url.QueryEscape(query)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil); if err != nil { return nil, err }
	req.Header.Set("X-API-Key", c.APIKey); req.Header.Set("Accept", "application/json")
	resp, err := c.HTTP.Do(req); if err != nil { return nil, err }; defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20)); if err != nil { return nil, err }
	if resp.StatusCode < 200 || resp.StatusCode >= 300 { return nil, fmt.Errorf("PesaGuard API returned HTTP %d", resp.StatusCode) }
	var result map[string]any; if err := json.Unmarshal(body, &result); err != nil { return nil, err }; return result, nil
}
