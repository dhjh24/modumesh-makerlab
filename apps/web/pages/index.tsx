import type { NextPage } from 'next';
import Head from 'next/head';

const Home: NextPage = () => {
  return (
    <div>
      <Head>
        <title>ModuMesh MakerLab</title>
        <meta name="description" content="Self-hosted 3D generator platform" />
      </Head>
      <main style={{ padding: '2rem' }}>
        <h1>ModuMesh MakerLab</h1>
        <p>Self-hosted 3D generator platform.</p>
        <p>
          <a href="/api/health">Health Check</a>
        </p>
      </main>
    </div>
  );
};

export default Home;
