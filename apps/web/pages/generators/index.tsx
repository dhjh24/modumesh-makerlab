import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import type { CatalogItem } from '@modumesh/shared-types';
import { AppShell } from '../../components/AppShell';
import { api, ApiError } from '../../lib/api';

const MATURITY_COLORS: Record<string, string> = {
  experimental: '#eab308',
  stable: '#22c55e',
  deprecated: '#ef4444',
};

function CapabilityBadge({ label, active }: { label: string; active?: boolean }) {
  if (!active) return null;
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: '0.7rem',
        padding: '1px 6px',
        borderRadius: 4,
        backgroundColor: '#1e293b',
        color: '#94a3b8',
        marginRight: 4,
        marginBottom: 4,
      }}
    >
      {label}
    </span>
  );
}

export default function MarketplacePage() {
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedMaturity, setSelectedMaturity] = useState('');

  const load = useCallback(async () => {
    setError(null);
    try {
      const [catalog, catResult] = await Promise.all([
        api.listCatalog({
          category: selectedCategory || undefined,
          maturity: selectedMaturity || undefined,
          search: search || undefined,
          limit: 50,
        }),
        api.listCatalogCategories(),
      ]);
      setItems(catalog.items);
      setTotal(catalog.total);
      setCategories(catResult.categories);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, [selectedCategory, selectedMaturity, search]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell title="Generator Marketplace">
      <Head>
        <title>Generator Marketplace · ModuMesh MakerLab</title>
      </Head>

      <h1 className="mm-h1">Generator Marketplace</h1>
      <p className="mm-lead">
        Browse, configure, and generate printable 3D parts. All generators work through the
        same schema-driven editor — no custom forms needed.
      </p>

      {/* Filters */}
      <div
        style={{
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          marginTop: '1rem',
          marginBottom: '1rem',
          alignItems: 'center',
        }}
      >
        <input
          className="mm-input"
          placeholder="Search generators…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: '1 1 200px', maxWidth: 320 }}
          aria-label="Search generators"
        />
        <select
          className="mm-input"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          style={{ width: 160 }}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          className="mm-input"
          value={selectedMaturity}
          onChange={(e) => setSelectedMaturity(e.target.value)}
          style={{ width: 160 }}
          aria-label="Filter by maturity"
        >
          <option value="">All maturity</option>
          <option value="experimental">Experimental</option>
          <option value="stable">Stable</option>
          <option value="deprecated">Deprecated</option>
        </select>
        <button className="mm-btn" onClick={() => void load()} style={{ padding: '8px 16px' }}>
          Refresh
        </button>
      </div>

      {/* Error */}
      {error ? (
        <div className="mm-panel" style={{ color: '#ef4444', marginTop: '1rem' }}>
          <p>{error}</p>
        </div>
      ) : null}

      {/* Grid */}
      {items === null ? (
        <p>Loading generators…</p>
      ) : items.length === 0 ? (
        <div className="mm-panel" style={{ marginTop: '1rem' }}>
          <p>
            {search || selectedCategory || selectedMaturity
              ? 'No generators match your filters.'
              : 'No generators available yet.'}
          </p>
        </div>
      ) : (
        <>
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '0.75rem' }}>
            {total} generator{total !== 1 ? 's' : ''}
          </p>
          <div className="mm-grid-3" style={{ marginTop: 0 }}>
            {items.map((item) => (
              <Link
                key={`${item.plugin_id}@${item.version}`}
                href={`/generators/${item.plugin_id}`}
                style={{ textDecoration: 'none' }}
              >
                <article
                  className="mm-panel"
                  style={{
                    cursor: 'pointer',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: 8,
                    }}
                  >
                    <h3 style={{ margin: 0, fontSize: '1rem' }}>{item.name}</h3>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        padding: '2px 8px',
                        borderRadius: 10,
                        backgroundColor: MATURITY_COLORS[item.maturity] || '#64748b',
                        color: '#fff',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.maturity}
                    </span>
                  </div>
                  {item.description ? (
                    <p
                      style={{
                        fontSize: '0.8125rem',
                        color: '#64748b',
                        margin: '0 0 8px 0',
                        flex: 1,
                      }}
                    >
                      {item.description}
                    </p>
                  ) : null}
                  <div style={{ marginBottom: 8 }}>
                    {item.categories.slice(0, 4).map((cat) => (
                      <CapabilityBadge key={cat} label={cat} active />
                    ))}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 4,
                      marginTop: 'auto',
                    }}
                  >
                    <CapabilityBadge label="text" active={item.capabilities.text} />
                    <CapabilityBadge label="image" active={item.capabilities.imageUpload} />
                    <CapabilityBadge label="multipart" active={item.capabilities.multipart} />
                    <CapabilityBadge label="multicolor" active={item.capabilities.multicolor} />
                    <CapabilityBadge label="preview" active={item.capabilities.preview} />
                    <CapabilityBadge label="deterministic" active={item.capabilities.deterministic} />
                    <CapabilityBadge label="shop" active={item.capabilities.shopReady} />
                  </div>
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: '0.75rem',
                      color: '#94a3b8',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>{item.engine}</span>
                    <span>
                      {item.license ? (
                        <span title={item.license_url || ''}>{item.license}</span>
                      ) : null}
                      {item.author ? ` · ${item.author}` : ''}
                    </span>
                  </div>
                </article>
              </Link>
            ))}
          </div>
        </>
      )}
    </AppShell>
  );
}
