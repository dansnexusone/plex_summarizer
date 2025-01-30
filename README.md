# Plex Summary Updater

A Python tool that automatically updates movie and TV show summaries in your Plex library using data from TMDB (The Movie Database). This tool supports multithreaded processing and provides real-time progress tracking.

## Features

- Automatically updates movie and TV show summaries from TMDB
- Uses TMDB IDs from Plex metadata when available
- Falls back to title-based search when TMDB ID isn't available
- Multithreaded processing for optimal performance
- Real-time progress tracking with tqdm
- Detailed status reporting and statistics
- Handles corporate proxy environments (supports SSL verification bypass)

## Requirements

- Python 3.9+
- Plex Media Server
- TMDB API key
- Plex authentication token

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/plex-summary-updater.git
   cd plex-summary-updater
   ```

2. Install the required packages:
   ```bash
   pip install plexapi python-dotenv requests tqdm
   ```

3. Create a `.env` file in the project root with your credentials:
   ```plaintext
   PLEX_URL=http://your-plex-server:32400
   PLEX_TOKEN=your-plex-token
   TMDB_API_KEY=your-tmdb-api-key
   ```

### Getting Your Credentials

- **Plex Token**: You can find your Plex token by following [Plex's official guide](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
- **TMDB API Key**: Sign up at [TMDB](https://www.themoviedb.org/documentation/api) and request an API key
- **Plex URL**: Your Plex server's URL (usually `http://localhost:32400` for local installations)

## Usage

Run the script:
```bash
python main.py
```


The script will:
1. Connect to your Plex server using the provided credentials
2. Iterate through all movie and TV show libraries
3. For each item:
   - First try to match using TMDB ID from Plex metadata
   - Fall back to title search if no TMDB ID is available
   - Update the summary if it differs from TMDB's version
4. Show progress bars and completion statistics

## Configuration

The script can be configured by modifying the following variables in `main.py`:

- `MAX_WORKERS`: Number of concurrent threads (default: 10)
- `TMDB_BASE_URL`: TMDB API base URL (default: "https://api.themoviedb.org/3")

## Status Codes

The script provides the following status codes for each processed item:

- `Updated`: Successfully updated the summary with new content
- `No change needed`: Current summary matches TMDB
- `No TMDB match found`: Could not find matching content on TMDB
- `Error: <message>`: Processing error with detailed message

## Technical Details

### API Endpoints Used

#### TMDB:
- `/movie/{id}`: Direct movie lookup by TMDB ID
- `/tv/{id}`: Direct TV show lookup by TMDB ID
- `/search/movie`: Movie search by title/year
- `/search/tv`: TV show search by title

### Threading

The script uses Python's ThreadPoolExecutor for concurrent processing:
- Default of 10 concurrent workers
- Each media item is processed in its own thread
- Progress is tracked across all threads

### Error Handling

- SSL verification is disabled (`verify=False`) to support corporate proxies
- Comprehensive exception handling prevents single item failures from affecting the entire process
- Detailed error messages are captured and reported

## Troubleshooting

Common issues and solutions:

1. **SSL Certificate Errors**:
   - The script disables SSL verification by default
   - If you need SSL verification, remove `verify=False` from the requests calls

2. **Rate Limiting**:
   - Adjust `MAX_WORKERS` if you encounter TMDB API rate limits
   - Default of 10 workers should work within standard API limits

3. **No Updates Occurring**:
   - Verify your TMDB API key is valid
   - Check your Plex token has sufficient permissions
   - Ensure your Plex URL is accessible

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.