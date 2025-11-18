/**
 * PodX API Client Example - JavaScript/Node.js
 *
 * This example demonstrates how to interact with the PodX API Server using JavaScript.
 *
 * Features demonstrated:
 * - File upload (Node.js)
 * - Job creation
 * - Real-time progress streaming (SSE)
 * - Job status checking
 * - Result retrieval
 * - Error handling
 *
 * Requirements:
 *     npm install node-fetch form-data eventsource
 *
 * Usage:
 *     node examples/javascript_client.js
 */

const fetch = require('node-fetch');
const FormData = require('form-data');
const EventSource = require('eventsource');
const fs = require('fs');
const path = require('path');

class PodXClient {
  /**
   * Initialize the PodX client
   * @param {string} baseUrl - Base URL of the PodX server
   * @param {string|null} apiKey - Optional API key for authentication
   */
  constructor(baseUrl = 'http://localhost:8000', apiKey = null) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = {
      'Content-Type': 'application/json',
    };
    if (apiKey) {
      this.headers['X-API-Key'] = apiKey;
    }
  }

  /**
   * Check server health
   * @returns {Promise<Object>} Health check response
   */
  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return await response.json();
  }

  /**
   * Upload an audio file
   * @param {string} filePath - Path to audio file
   * @returns {Promise<string>} Upload ID
   */
  async uploadFile(filePath) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filePath}`);
    }

    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath), {
      filename: path.basename(filePath),
      contentType: 'audio/mpeg',
    });

    const headers = { ...this.headers };
    delete headers['Content-Type']; // Let FormData set it

    if (this.headers['X-API-Key']) {
      headers['X-API-Key'] = this.headers['X-API-Key'];
    }

    const response = await fetch(`${this.baseUrl}/upload`, {
      method: 'POST',
      body: formData,
      headers: headers,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`✓ Uploaded: ${path.basename(filePath)} (${data.size_mb.toFixed(1)} MB)`);
    return data.upload_id;
  }

  /**
   * Create a processing job
   * @param {Object} options - Job options
   * @param {string|null} options.uploadId - ID of uploaded file (optional)
   * @param {string|null} options.url - URL to podcast episode (optional)
   * @param {string} options.profile - Processing profile (quick, medium, full, hq)
   * @returns {Promise<string>} Job ID
   */
  async createJob({ uploadId = null, url = null, profile = 'quick' } = {}) {
    if (!uploadId && !url) {
      throw new Error('Must provide either uploadId or url');
    }

    const payload = { profile };
    if (uploadId) payload.upload_id = uploadId;
    if (url) payload.url = url;

    const response = await fetch(`${this.baseUrl}/jobs`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Create job failed: ${response.statusText}`);
    }

    const data = await response.json();
    console.log(`✓ Job created: ${data.job_id}`);
    return data.job_id;
  }

  /**
   * Get job status and details
   * @param {string} jobId - Job ID
   * @returns {Promise<Object>} Job details
   */
  async getJob(jobId) {
    const response = await fetch(`${this.baseUrl}/jobs/${jobId}`, {
      headers: this.headers,
    });

    if (!response.ok) {
      throw new Error(`Get job failed: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Stream real-time job progress via Server-Sent Events
   * @param {string} jobId - Job ID
   * @param {Function} onUpdate - Callback for progress updates
   * @returns {Promise<void>}
   */
  streamProgress(jobId, onUpdate) {
    return new Promise((resolve, reject) => {
      const url = `${this.baseUrl}/jobs/${jobId}/stream`;

      // Add API key to URL if needed
      const headers = {};
      if (this.headers['X-API-Key']) {
        headers['X-API-Key'] = this.headers['X-API-Key'];
      }

      const eventSource = new EventSource(url, { headers });

      console.log(`📡 Streaming progress for job ${jobId}...`);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // Call update callback
        if (onUpdate) {
          onUpdate(data);
        }

        // Print progress update
        if (data.status === 'in_progress') {
          const step = data.current_step || 'processing';
          const progress = data.progress || 0;
          console.log(`  [${progress.toString().padStart(3)}%] ${step}`);
        } else if (data.status === 'completed') {
          console.log('✓ Job completed!');
          eventSource.close();
          resolve(data);
        } else if (data.status === 'failed') {
          const error = data.error || 'Unknown error';
          console.log(`✗ Job failed: ${error}`);
          eventSource.close();
          reject(new Error(error));
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
        reject(error);
      };
    });
  }

  /**
   * Wait for a job to complete (polling)
   * @param {string} jobId - Job ID
   * @param {number} checkInterval - Milliseconds between status checks
   * @returns {Promise<Object>} Final job details
   */
  async waitForJob(jobId, checkInterval = 5000) {
    console.log(`⏳ Waiting for job ${jobId}...`);

    while (true) {
      const job = await this.getJob(jobId);
      const status = job.status;

      if (status === 'completed') {
        console.log('✓ Job completed!');
        return job;
      } else if (status === 'failed') {
        const error = job.error || 'Unknown error';
        console.log(`✗ Job failed: ${error}`);
        throw new Error(`Job failed: ${error}`);
      } else if (status === 'pending' || status === 'in_progress') {
        const progress = job.progress || 0;
        const step = job.current_step || 'processing';
        console.log(`  [${progress.toString().padStart(3)}%] ${step}`);
        await new Promise((resolve) => setTimeout(resolve, checkInterval));
      } else {
        console.log(`  Unknown status: ${status}`);
        await new Promise((resolve) => setTimeout(resolve, checkInterval));
      }
    }
  }

  /**
   * List recent jobs
   * @param {number} limit - Maximum number of jobs to return
   * @returns {Promise<Object>} List of jobs
   */
  async listJobs(limit = 10) {
    const response = await fetch(`${this.baseUrl}/jobs?limit=${limit}`, {
      headers: this.headers,
    });

    if (!response.ok) {
      throw new Error(`List jobs failed: ${response.statusText}`);
    }

    return await response.json();
  }
}

// Example usage
async function main() {
  try {
    // Initialize client
    const client = new PodXClient(
      'http://localhost:8000',
      null // Set API key if authentication is enabled
    );

    // Check server health
    console.log('1. Checking server health...');
    const health = await client.healthCheck();
    console.log(`   Server status: ${health.status}`);
    console.log(`   Version: ${health.version}`);
    console.log();

    // Example 1: Process from URL
    console.log('2. Creating job from URL...');
    const jobId = await client.createJob({
      url: 'https://example.com/podcast.mp3',
      profile: 'quick',
    });
    console.log();

    // Example 2: Upload file and create job
    // console.log('2. Uploading audio file...');
    // const uploadId = await client.uploadFile('path/to/your/audio.mp3');
    // console.log();
    //
    // console.log('3. Creating processing job...');
    // const jobId = await client.createJob({ uploadId, profile: 'quick' });
    // console.log();

    // Example 3a: Stream real-time progress (recommended)
    console.log('3a. Streaming real-time progress...');
    await client.streamProgress(jobId, (update) => {
      // Handle progress updates here if needed
      // Updates are also printed automatically
    });
    console.log();

    // Example 3b: Poll for completion (alternative)
    // console.log('3b. Polling for job completion...');
    // const job = await client.waitForJob(jobId, 5000);
    // console.log();

    // Get final job details
    console.log('4. Fetching job details...');
    const job = await client.getJob(jobId);
    console.log(`   Status: ${job.status}`);
    console.log(`   Profile: ${job.profile}`);
    if (job.result) {
      console.log(`   Result: ${job.result}`);
    }
    console.log();

    // List recent jobs
    console.log('5. Listing recent jobs...');
    const jobs = await client.listJobs(5);
    console.log(`   Found ${jobs.jobs.length} jobs:`);
    for (const j of jobs.jobs) {
      console.log(`     - ${j.id}: ${j.status} (${j.profile})`);
    }
    console.log();

    console.log('✓ Example completed!');
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Run the example
if (require.main === module) {
  main();
}

// Export for use as a module
module.exports = { PodXClient };
