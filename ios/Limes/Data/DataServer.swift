import Foundation

/// The published data (manifest.json and the `.sqlite.zst` files) at `baseURL`.
/// The manifest is kept in `dir` with its ETag, so an unchanged manifest costs
/// a 304 with no body.
struct DataServer {
    let baseURL: URL
    let dir: URL

    private var manifestFile: URL { dir.appendingPathComponent("manifest.json") }
    private var etagFile: URL { dir.appendingPathComponent("manifest.etag") }

    struct HTTPError: Error {
        let path: String
        let status: Int
    }

    /// The current manifest, fetched or revalidated.
    func manifest(wifiOnly: Bool) async throws -> String {
        var request = self.request("manifest.json", wifiOnly: wifiOnly)
        request.timeoutInterval = 15
        let cached = cachedManifest()
        if cached != nil, let etag = try? String(contentsOf: etagFile, encoding: .utf8) {
            request.setValue(etag, forHTTPHeaderField: "If-None-Match")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        let http = response as? HTTPURLResponse
        switch http?.statusCode {
        case 304:
            guard let cached else { throw HTTPError(path: "manifest.json", status: 304) }
            return cached
        case 200:
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try data.write(to: manifestFile, options: .atomic)
            if let etag = http?.value(forHTTPHeaderField: "ETag") {
                try? etag.write(to: etagFile, atomically: true, encoding: .utf8)
            } else {
                try? FileManager.default.removeItem(at: etagFile)
            }
            return String(decoding: data, as: UTF8.self)
        default:
            throw HTTPError(path: "manifest.json", status: http?.statusCode ?? 0)
        }
    }

    /// The manifest last fetched, for showing sizes without the network.
    func cachedManifest() -> String? {
        try? String(contentsOf: manifestFile, encoding: .utf8)
    }

    /// Downloads a published file (path relative to the manifest) to `out`.
    func download(_ path: String, to out: URL, wifiOnly: Bool) async throws {
        let (temporary, response) = try await URLSession.shared.download(for: request(path, wifiOnly: wifiOnly))
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
            try? FileManager.default.removeItem(at: temporary)
            throw HTTPError(path: path, status: status)
        }
        let files = FileManager.default
        try files.createDirectory(at: out.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? files.removeItem(at: out)
        try files.moveItem(at: temporary, to: out)
    }

    private func request(_ path: String, wifiOnly: Bool) -> URLRequest {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        // The ETag is handled here, not by the URL cache.
        request.cachePolicy = .reloadIgnoringLocalCacheData
        if wifiOnly {
            request.allowsExpensiveNetworkAccess = false
            request.allowsConstrainedNetworkAccess = false
        }
        return request
    }
}
