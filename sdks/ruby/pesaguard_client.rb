# frozen_string_literal: true
require 'net/http'
require 'uri'
require 'json'

class PesaGuardClient
  BASE_URLS = { 'sandbox' => 'https://sandbox-api.pesaguard.co.ke', 'production' => 'https://api.pesaguard.co.ke' }.freeze

  def initialize(api_key: ENV.fetch('PESAGUARD_API_KEY', ''), environment: ENV.fetch('PESAGUARD_ENV', 'sandbox'), timeout: 10)
    raise ArgumentError, 'environment must be sandbox or production' unless BASE_URLS.key?(environment)
    prefix = environment == 'sandbox' ? 'pg_sandbox_' : 'pg_live_'
    raise ArgumentError, "selected environment requires a #{prefix} API key" unless api_key.start_with?(prefix)
    @api_key, @timeout = api_key, timeout
    @base_url = ENV.fetch('PESAGUARD_BASE_URL', BASE_URLS.fetch(environment)).sub(%r{/+$}, '')
    raise ArgumentError, 'base URL does not match selected environment' unless URI(@base_url).host == URI(BASE_URLS.fetch(environment)).host
  end

  def search_registry(query)
    uri = URI("#{@base_url}/api/v1/registry/search")
    uri.query = URI.encode_www_form(q: query)
    request = Net::HTTP::Get.new(uri)
    request['X-API-Key'] = @api_key
    request['Accept'] = 'application/json'
    response = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https', open_timeout: 5, read_timeout: @timeout) { |http| http.request(request) }
    raise "PesaGuard API returned HTTP #{response.code}" unless response.is_a?(Net::HTTPSuccess)
    JSON.parse(response.body)
  end
end
