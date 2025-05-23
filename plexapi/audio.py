# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from typing import Any, Dict, List, Optional, TypeVar

from plexapi import media, utils
from plexapi.base import Playable, PlexPartialObject, PlexHistory, PlexSession, cached_data_property
from plexapi.exceptions import BadRequest
from plexapi.mixins import (
    AdvancedSettingsMixin, SplitMergeMixin, UnmatchMatchMixin, ExtrasMixin, HubsMixin, PlayedUnplayedMixin, RatingMixin,
    ArtUrlMixin, ArtMixin, PosterUrlMixin, PosterMixin, ThemeMixin, ThemeUrlMixin,
    ArtistEditMixins, AlbumEditMixins, TrackEditMixins
)
from plexapi.playlist import Playlist


TAudio = TypeVar("TAudio", bound="Audio")
TTrack = TypeVar("TTrack", bound="Track")


class Audio(PlexPartialObject, PlayedUnplayedMixin):
    """ Base class for all audio objects including :class:`~plexapi.audio.Artist`,
        :class:`~plexapi.audio.Album`, and :class:`~plexapi.audio.Track`.

        Attributes:
            addedAt (datetime): Datetime the item was added to the library.
            art (str): URL to artwork image (/library/metadata/<ratingKey>/art/<artid>).
            artBlurHash (str): BlurHash string for artwork image.
            distance (float): Sonic Distance of the item from the seed item.
            fields (List<:class:`~plexapi.media.Field`>): List of field objects.
            guid (str): Plex GUID for the artist, album, or track (plex://artist/5d07bcb0403c64029053ac4c).
            images (List<:class:`~plexapi.media.Image`>): List of image objects.
            index (int): Plex index number (often the track number).
            key (str): API URL (/library/metadata/<ratingkey>).
            lastRatedAt (datetime): Datetime the item was last rated.
            lastViewedAt (datetime): Datetime the item was last played.
            librarySectionID (int): :class:`~plexapi.library.LibrarySection` ID.
            librarySectionKey (str): :class:`~plexapi.library.LibrarySection` key.
            librarySectionTitle (str): :class:`~plexapi.library.LibrarySection` title.
            listType (str): Hardcoded as 'audio' (useful for search filters).
            moods (List<:class:`~plexapi.media.Mood`>): List of mood objects.
            musicAnalysisVersion (int): The Plex music analysis version for the item.
            ratingKey (int): Unique key identifying the item.
            summary (str): Summary of the artist, album, or track.
            thumb (str): URL to thumbnail image (/library/metadata/<ratingKey>/thumb/<thumbid>).
            thumbBlurHash (str): BlurHash string for thumbnail image.
            title (str): Name of the artist, album, or track (Jason Mraz, We Sing, Lucky, etc.).
            titleSort (str): Title to use when sorting (defaults to title).
            type (str): 'artist', 'album', or 'track'.
            updatedAt (datetime): Datetime the item was updated.
            userRating (float): Rating of the item (0.0 - 10.0) equaling (0 stars - 5 stars).
            viewCount (int): Count of times the item was played.
    """
    METADATA_TYPE = 'track'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        self.addedAt = utils.toDatetime(data.attrib.get('addedAt'))
        self.art = data.attrib.get('art')
        self.artBlurHash = data.attrib.get('artBlurHash')
        self.distance = utils.cast(float, data.attrib.get('distance'))
        self.guid = data.attrib.get('guid')
        self.index = utils.cast(int, data.attrib.get('index'))
        self.key = data.attrib.get('key', '')
        self.lastRatedAt = utils.toDatetime(data.attrib.get('lastRatedAt'))
        self.lastViewedAt = utils.toDatetime(data.attrib.get('lastViewedAt'))
        self.librarySectionID = utils.cast(int, data.attrib.get('librarySectionID'))
        self.librarySectionKey = data.attrib.get('librarySectionKey')
        self.librarySectionTitle = data.attrib.get('librarySectionTitle')
        self.listType = 'audio'
        self.musicAnalysisVersion = utils.cast(int, data.attrib.get('musicAnalysisVersion'))
        self.ratingKey = utils.cast(int, data.attrib.get('ratingKey'))
        self.summary = data.attrib.get('summary')
        self.thumb = data.attrib.get('thumb')
        self.thumbBlurHash = data.attrib.get('thumbBlurHash')
        self.title = data.attrib.get('title')
        self.titleSort = data.attrib.get('titleSort', self.title)
        self.type = data.attrib.get('type')
        self.updatedAt = utils.toDatetime(data.attrib.get('updatedAt'))
        self.userRating = utils.cast(float, data.attrib.get('userRating'))
        self.viewCount = utils.cast(int, data.attrib.get('viewCount', 0))

    @cached_data_property
    def fields(self):
        return self.findItems(self._data, media.Field)

    @cached_data_property
    def images(self):
        return self.findItems(self._data, media.Image)

    @cached_data_property
    def moods(self):
        return self.findItems(self._data, media.Mood)

    def url(self, part):
        """ Returns the full URL for the audio item. Typically used for getting a specific track. """
        return self._server.url(part, includeToken=True) if part else None

    def _defaultSyncTitle(self):
        """ Returns str, default title for a new syncItem. """
        return self.title

    @property
    def hasSonicAnalysis(self):
        """ Returns True if the audio has been sonically analyzed. """
        return self.musicAnalysisVersion == 1

    def sync(self, bitrate, client=None, clientId=None, limit=None, title=None):
        """ Add current audio (artist, album or track) as sync item for specified device.
            See :func:`~plexapi.myplex.MyPlexAccount.sync` for possible exceptions.

            Parameters:
                bitrate (int): maximum bitrate for synchronized music, better use one of MUSIC_BITRATE_* values from the
                               module :mod:`~plexapi.sync`.
                client (:class:`~plexapi.myplex.MyPlexDevice`): sync destination, see
                                                               :func:`~plexapi.myplex.MyPlexAccount.sync`.
                clientId (str): sync destination, see :func:`~plexapi.myplex.MyPlexAccount.sync`.
                limit (int): maximum count of items to sync, unlimited if `None`.
                title (str): descriptive title for the new :class:`~plexapi.sync.SyncItem`, if empty the value would be
                             generated from metadata of current media.

            Returns:
                :class:`~plexapi.sync.SyncItem`: an instance of created syncItem.
        """

        from plexapi.sync import SyncItem, Policy, MediaSettings

        myplex = self._server.myPlexAccount()
        sync_item = SyncItem(self._server, None)
        sync_item.title = title if title else self._defaultSyncTitle()
        sync_item.rootTitle = self.title
        sync_item.contentType = self.listType
        sync_item.metadataType = self.METADATA_TYPE
        sync_item.machineIdentifier = self._server.machineIdentifier

        section = self._server.library.sectionByID(self.librarySectionID)

        sync_item.location = f'library://{section.uuid}/item/{quote_plus(self.key)}'
        sync_item.policy = Policy.create(limit)
        sync_item.mediaSettings = MediaSettings.createMusic(bitrate)

        return myplex.sync(sync_item, client=client, clientId=clientId)

    def sonicallySimilar(
        self: TAudio,
        limit: Optional[int] = None,
        maxDistance: Optional[float] = None,
        **kwargs,
    ) -> List[TAudio]:
        """Returns a list of sonically similar audio items.

        Parameters:
            limit (int): Maximum count of items to return. Default 50 (server default)
            maxDistance (float): Maximum distance between tracks, 0.0 - 1.0. Default 0.25 (server default).
            **kwargs: Additional options passed into :func:`~plexapi.base.PlexObject.fetchItems`.

        Returns:
            List[:class:`~plexapi.audio.Audio`]: list of sonically similar audio items.
        """

        key = f"{self.key}/nearest"
        params: Dict[str, Any] = {}
        if limit is not None:
            params['limit'] = limit
        if maxDistance is not None:
            params['maxDistance'] = maxDistance
        key += utils.joinArgs(params)

        return self.fetchItems(
            key,
            cls=type(self),
            **kwargs,
        )


@utils.registerPlexObject
class Artist(
    Audio,
    AdvancedSettingsMixin, SplitMergeMixin, UnmatchMatchMixin, ExtrasMixin, HubsMixin, RatingMixin,
    ArtMixin, PosterMixin, ThemeMixin,
    ArtistEditMixins
):
    """ Represents a single Artist.

        Attributes:
            TAG (str): 'Directory'
            TYPE (str): 'artist'
            albumSort (int): Setting that indicates how albums are sorted for the artist
                (-1 = Library default, 0 = Newest first, 1 = Oldest first, 2 = By name).
            audienceRating (float): Audience rating.
            collections (List<:class:`~plexapi.media.Collection`>): List of collection objects.
            countries (List<:class:`~plexapi.media.Country`>): List country objects.
            genres (List<:class:`~plexapi.media.Genre`>): List of genre objects.
            guids (List<:class:`~plexapi.media.Guid`>): List of guid objects.
            key (str): API URL (/library/metadata/<ratingkey>).
            labels (List<:class:`~plexapi.media.Label`>): List of label objects.
            locations (List<str>): List of folder paths where the artist is found on disk.
            rating (float): Artist rating (7.9; 9.8; 8.1).
            similar (List<:class:`~plexapi.media.Similar`>): List of similar objects.
            styles (List<:class:`~plexapi.media.Style`>): List of style objects.
            theme (str): URL to theme resource (/library/metadata/<ratingkey>/theme/<themeid>).
            ultraBlurColors (:class:`~plexapi.media.UltraBlurColors`): Ultra blur color object.
    """
    TAG = 'Directory'
    TYPE = 'artist'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        Audio._loadData(self, data)
        self.albumSort = utils.cast(int, data.attrib.get('albumSort', '-1'))
        self.audienceRating = utils.cast(float, data.attrib.get('audienceRating'))
        self.key = self.key.replace('/children', '')  # FIX_BUG_50
        self.rating = utils.cast(float, data.attrib.get('rating'))
        self.theme = data.attrib.get('theme')

    @cached_data_property
    def collections(self):
        return self.findItems(self._data, media.Collection)

    @cached_data_property
    def countries(self):
        return self.findItems(self._data, media.Country)

    @cached_data_property
    def genres(self):
        return self.findItems(self._data, media.Genre)

    @cached_data_property
    def guids(self):
        return self.findItems(self._data, media.Guid)

    @cached_data_property
    def labels(self):
        return self.findItems(self._data, media.Label)

    @cached_data_property
    def locations(self):
        return self.listAttrs(self._data, 'path', etag='Location')

    @cached_data_property
    def similar(self):
        return self.findItems(self._data, media.Similar)

    @cached_data_property
    def styles(self):
        return self.findItems(self._data, media.Style)

    @cached_data_property
    def ultraBlurColors(self):
        return self.findItem(self._data, media.UltraBlurColors)

    def __iter__(self):
        for album in self.albums():
            yield album

    def album(self, title):
        """ Returns the :class:`~plexapi.audio.Album` that matches the specified title.

            Parameters:
                title (str): Title of the album to return.
        """
        return self.section().get(
            title=title,
            libtype='album',
            filters={'artist.id': self.ratingKey}
        )

    def albums(self, **kwargs):
        """ Returns a list of :class:`~plexapi.audio.Album` objects by the artist. """
        return self.section().search(
            libtype='album',
            filters={**kwargs.pop('filters', {}), 'artist.id': self.ratingKey},
            **kwargs
        )

    def track(self, title=None, album=None, track=None):
        """ Returns the :class:`~plexapi.audio.Track` that matches the specified title.

            Parameters:
                title (str): Title of the track to return.
                album (str): Album name (default: None; required if title not specified).
                track (int): Track number (default: None; required if title not specified).

            Raises:
                :exc:`~plexapi.exceptions.BadRequest`: If title or album and track parameters are missing.
        """
        key = f'{self.key}/allLeaves'
        if title is not None:
            return self.fetchItem(key, Track, title__iexact=title)
        elif album is not None and track is not None:
            return self.fetchItem(key, Track, parentTitle__iexact=album, index=track)
        raise BadRequest('Missing argument: title or album and track are required')

    def tracks(self, **kwargs):
        """ Returns a list of :class:`~plexapi.audio.Track` objects by the artist. """
        key = f'{self.key}/allLeaves'
        return self.fetchItems(key, Track, **kwargs)

    def get(self, title=None, album=None, track=None):
        """ Alias of :func:`~plexapi.audio.Artist.track`. """
        return self.track(title, album, track)

    def download(self, savepath=None, keep_original_name=False, subfolders=False, **kwargs):
        """ Download all tracks from the artist. See :func:`~plexapi.base.Playable.download` for details.

            Parameters:
                savepath (str): Defaults to current working dir.
                keep_original_name (bool): True to keep the original filename otherwise
                    a friendlier filename is generated.
                subfolders (bool): True to separate tracks in to album folders.
                **kwargs: Additional options passed into :func:`~plexapi.base.PlexObject.getStreamURL`.
        """
        filepaths = []
        for track in self.tracks():
            _savepath = os.path.join(savepath, track.parentTitle) if subfolders else savepath
            filepaths += track.download(_savepath, keep_original_name, **kwargs)
        return filepaths

    def popularTracks(self):
        """ Returns a list of :class:`~plexapi.audio.Track` popular tracks by the artist. """
        filters = {
            'album.subformat!': 'Compilation,Live',
            'artist.id': self.ratingKey,
            'group': 'title',
            'ratingCount>>': 0,
        }
        return self.section().search(
            libtype='track',
            filters=filters,
            sort='ratingCount:desc',
            limit=100
        )

    def station(self):
        """ Returns a :class:`~plexapi.playlist.Playlist` artist radio station or `None`. """
        key = f'{self.key}?includeStations=1'
        return next(iter(self.fetchItems(key, cls=Playlist, rtag="Stations")), None)

    @property
    def metadataDirectory(self):
        """ Returns the Plex Media Server data directory where the metadata is stored. """
        guid_hash = utils.sha1hash(self.guid)
        return str(Path('Metadata') / 'Artists' / guid_hash[0] / f'{guid_hash[1:]}.bundle')


@utils.registerPlexObject
class Album(
    Audio,
    SplitMergeMixin, UnmatchMatchMixin, RatingMixin,
    ArtMixin, PosterMixin, ThemeUrlMixin,
    AlbumEditMixins
):
    """ Represents a single Album.

        Attributes:
            TAG (str): 'Directory'
            TYPE (str): 'album'
            audienceRating (float): Audience rating.
            collections (List<:class:`~plexapi.media.Collection`>): List of collection objects.
            formats (List<:class:`~plexapi.media.Format`>): List of format objects.
            genres (List<:class:`~plexapi.media.Genre`>): List of genre objects.
            guids (List<:class:`~plexapi.media.Guid`>): List of guid objects.
            key (str): API URL (/library/metadata/<ratingkey>).
            labels (List<:class:`~plexapi.media.Label`>): List of label objects.
            leafCount (int): Number of items in the album view.
            loudnessAnalysisVersion (int): The Plex loudness analysis version level.
            originallyAvailableAt (datetime): Datetime the album was released.
            parentGuid (str): Plex GUID for the album artist (plex://artist/5d07bcb0403c64029053ac4c).
            parentKey (str): API URL of the album artist (/library/metadata/<parentRatingKey>).
            parentRatingKey (int): Unique key identifying the album artist.
            parentTheme (str): URL to artist theme resource (/library/metadata/<parentRatingkey>/theme/<themeid>).
            parentThumb (str): URL to album artist thumbnail image (/library/metadata/<parentRatingKey>/thumb/<thumbid>).
            parentTitle (str): Name of the album artist.
            rating (float): Album rating (7.9; 9.8; 8.1).
            studio (str): Studio that released the album.
            styles (List<:class:`~plexapi.media.Style`>): List of style objects.
            subformats (List<:class:`~plexapi.media.Subformat`>): List of subformat objects.
            ultraBlurColors (:class:`~plexapi.media.UltraBlurColors`): Ultra blur color object.
            viewedLeafCount (int): Number of items marked as played in the album view.
            year (int): Year the album was released.
    """
    TAG = 'Directory'
    TYPE = 'album'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        Audio._loadData(self, data)
        self.audienceRating = utils.cast(float, data.attrib.get('audienceRating'))
        self.key = self.key.replace('/children', '')  # FIX_BUG_50
        self.leafCount = utils.cast(int, data.attrib.get('leafCount'))
        self.loudnessAnalysisVersion = utils.cast(int, data.attrib.get('loudnessAnalysisVersion'))
        self.originallyAvailableAt = utils.toDatetime(data.attrib.get('originallyAvailableAt'), '%Y-%m-%d')
        self.parentGuid = data.attrib.get('parentGuid')
        self.parentKey = data.attrib.get('parentKey')
        self.parentRatingKey = utils.cast(int, data.attrib.get('parentRatingKey'))
        self.parentTheme = data.attrib.get('parentTheme')
        self.parentThumb = data.attrib.get('parentThumb')
        self.parentTitle = data.attrib.get('parentTitle')
        self.rating = utils.cast(float, data.attrib.get('rating'))
        self.studio = data.attrib.get('studio')
        self.viewedLeafCount = utils.cast(int, data.attrib.get('viewedLeafCount'))
        self.year = utils.cast(int, data.attrib.get('year'))

    @cached_data_property
    def collections(self):
        return self.findItems(self._data, media.Collection)

    @cached_data_property
    def formats(self):
        return self.findItems(self._data, media.Format)

    @cached_data_property
    def genres(self):
        return self.findItems(self._data, media.Genre)

    @cached_data_property
    def guids(self):
        return self.findItems(self._data, media.Guid)

    @cached_data_property
    def labels(self):
        return self.findItems(self._data, media.Label)

    @cached_data_property
    def styles(self):
        return self.findItems(self._data, media.Style)

    @cached_data_property
    def subformats(self):
        return self.findItems(self._data, media.Subformat)

    @cached_data_property
    def ultraBlurColors(self):
        return self.findItem(self._data, media.UltraBlurColors)

    def __iter__(self):
        for track in self.tracks():
            yield track

    def track(self, title=None, track=None):
        """ Returns the :class:`~plexapi.audio.Track` that matches the specified title.

            Parameters:
                title (str): Title of the track to return.
                track (int): Track number (default: None; required if title not specified).

            Raises:
                :exc:`~plexapi.exceptions.BadRequest`: If title or track parameter is missing.
        """
        key = f'{self.key}/children'
        if title is not None and not isinstance(title, int):
            return self.fetchItem(key, Track, title__iexact=title)
        elif track is not None or isinstance(title, int):
            if isinstance(title, int):
                index = title
            else:
                index = track
            return self.fetchItem(key, Track, parentTitle__iexact=self.title, index=index)
        raise BadRequest('Missing argument: title or track is required')

    def tracks(self, **kwargs):
        """ Returns a list of :class:`~plexapi.audio.Track` objects in the album. """
        key = f'{self.key}/children'
        return self.fetchItems(key, Track, **kwargs)

    def get(self, title=None, track=None):
        """ Alias of :func:`~plexapi.audio.Album.track`. """
        return self.track(title, track)

    def artist(self):
        """ Return the album's :class:`~plexapi.audio.Artist`. """
        return self.fetchItem(self.parentKey)

    def download(self, savepath=None, keep_original_name=False, **kwargs):
        """ Download all tracks from the album. See :func:`~plexapi.base.Playable.download` for details.

            Parameters:
                savepath (str): Defaults to current working dir.
                keep_original_name (bool): True to keep the original filename otherwise
                    a friendlier filename is generated.
                **kwargs: Additional options passed into :func:`~plexapi.base.PlexObject.getStreamURL`.
        """
        filepaths = []
        for track in self.tracks():
            filepaths += track.download(savepath, keep_original_name, **kwargs)
        return filepaths

    def _defaultSyncTitle(self):
        """ Returns str, default title for a new syncItem. """
        return f'{self.parentTitle} - {self.title}'

    @property
    def metadataDirectory(self):
        """ Returns the Plex Media Server data directory where the metadata is stored. """
        guid_hash = utils.sha1hash(self.guid)
        return str(Path('Metadata') / 'Albums' / guid_hash[0] / f'{guid_hash[1:]}.bundle')


@utils.registerPlexObject
class Track(
    Audio, Playable,
    ExtrasMixin, RatingMixin,
    ArtUrlMixin, PosterUrlMixin, ThemeUrlMixin,
    TrackEditMixins
):
    """ Represents a single Track.

        Attributes:
            TAG (str): 'Directory'
            TYPE (str): 'track'
            audienceRating (float): Audience rating.
            chapters (List<:class:`~plexapi.media.Chapter`>): List of Chapter objects.
            chapterSource (str): Unknown
            collections (List<:class:`~plexapi.media.Collection`>): List of collection objects.
            duration (int): Length of the track in milliseconds.
            genres (List<:class:`~plexapi.media.Genre`>): List of genre objects.
            grandparentArt (str): URL to album artist artwork (/library/metadata/<grandparentRatingKey>/art/<artid>).
            grandparentGuid (str): Plex GUID for the album artist (plex://artist/5d07bcb0403c64029053ac4c).
            grandparentKey (str): API URL of the album artist (/library/metadata/<grandparentRatingKey>).
            grandparentRatingKey (int): Unique key identifying the album artist.
            grandparentTheme (str): URL to artist theme resource  (/library/metadata/<grandparentRatingkey>/theme/<themeid>).
                (/library/metadata/<grandparentRatingkey>/theme/<themeid>).
            grandparentThumb (str): URL to album artist thumbnail image
                (/library/metadata/<grandparentRatingKey>/thumb/<thumbid>).
            grandparentTitle (str): Name of the album artist for the track.
            guids (List<:class:`~plexapi.media.Guid`>): List of guid objects.
            labels (List<:class:`~plexapi.media.Label`>): List of label objects.
            media (List<:class:`~plexapi.media.Media`>): List of media objects.
            originalTitle (str): The artist for the track.
            parentGuid (str): Plex GUID for the album (plex://album/5d07cd8e403c640290f180f9).
            parentIndex (int): Disc number of the track.
            parentKey (str): API URL of the album (/library/metadata/<parentRatingKey>).
            parentRatingKey (int): Unique key identifying the album.
            parentThumb (str): URL to album thumbnail image (/library/metadata/<parentRatingKey>/thumb/<thumbid>).
            parentTitle (str): Name of the album for the track.
            primaryExtraKey (str) API URL for the primary extra for the track.
            rating (float): Track rating (7.9; 9.8; 8.1).
            ratingCount (int): Number of listeners who have scrobbled this track, as reported by Last.fm.
            skipCount (int): Number of times the track has been skipped.
            sourceURI (str): Remote server URI (server://<machineIdentifier>/com.plexapp.plugins.library)
                (remote playlist item only).
            viewOffset (int): View offset in milliseconds.
            year (int): Year the track was released.
    """
    TAG = 'Track'
    TYPE = 'track'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        Audio._loadData(self, data)
        Playable._loadData(self, data)
        self.audienceRating = utils.cast(float, data.attrib.get('audienceRating'))
        self.chapterSource = data.attrib.get('chapterSource')
        self.duration = utils.cast(int, data.attrib.get('duration'))
        self.grandparentArt = data.attrib.get('grandparentArt')
        self.grandparentGuid = data.attrib.get('grandparentGuid')
        self.grandparentKey = data.attrib.get('grandparentKey')
        self.grandparentRatingKey = utils.cast(int, data.attrib.get('grandparentRatingKey'))
        self.grandparentTheme = data.attrib.get('grandparentTheme')
        self.grandparentThumb = data.attrib.get('grandparentThumb')
        self.grandparentTitle = data.attrib.get('grandparentTitle')
        self.originalTitle = data.attrib.get('originalTitle')
        self.parentGuid = data.attrib.get('parentGuid')
        self.parentIndex = utils.cast(int, data.attrib.get('parentIndex'))
        self.parentKey = data.attrib.get('parentKey')
        self.parentRatingKey = utils.cast(int, data.attrib.get('parentRatingKey'))
        self.parentThumb = data.attrib.get('parentThumb')
        self.parentTitle = data.attrib.get('parentTitle')
        self.primaryExtraKey = data.attrib.get('primaryExtraKey')
        self.rating = utils.cast(float, data.attrib.get('rating'))
        self.ratingCount = utils.cast(int, data.attrib.get('ratingCount'))
        self.skipCount = utils.cast(int, data.attrib.get('skipCount'))
        self.sourceURI = data.attrib.get('source')  # remote playlist item
        self.viewOffset = utils.cast(int, data.attrib.get('viewOffset', 0))
        self.year = utils.cast(int, data.attrib.get('year'))

    @cached_data_property
    def chapters(self):
        return self.findItems(self._data, media.Chapter)

    @cached_data_property
    def collections(self):
        return self.findItems(self._data, media.Collection)

    @cached_data_property
    def genres(self):
        return self.findItems(self._data, media.Genre)

    @cached_data_property
    def guids(self):
        return self.findItems(self._data, media.Guid)

    @cached_data_property
    def labels(self):
        return self.findItems(self._data, media.Label)

    @cached_data_property
    def media(self):
        return self.findItems(self._data, media.Media)

    @property
    def locations(self):
        """ This does not exist in plex xml response but is added to have a common
            interface to get the locations of the track.

            Returns:
                List<str> of file paths where the track is found on disk.
        """
        return [part.file for part in self.iterParts() if part]

    @property
    def trackNumber(self):
        """ Returns the track number. """
        return self.index

    def _prettyfilename(self):
        """ Returns a filename for use in download. """
        return f'{self.grandparentTitle} - {self.parentTitle} - {str(self.trackNumber).zfill(2)} - {self.title}'

    def album(self):
        """ Return the track's :class:`~plexapi.audio.Album`. """
        return self.fetchItem(self.parentKey)

    def artist(self):
        """ Return the track's :class:`~plexapi.audio.Artist`. """
        return self.fetchItem(self.grandparentKey)

    def _defaultSyncTitle(self):
        """ Returns str, default title for a new syncItem. """
        return f'{self.grandparentTitle} - {self.parentTitle} - {self.title}'

    def _getWebURL(self, base=None):
        """ Get the Plex Web URL with the correct parameters. """
        return self._server._buildWebURL(base=base, endpoint='details', key=self.parentKey)

    @property
    def metadataDirectory(self):
        """ Returns the Plex Media Server data directory where the metadata is stored. """
        guid_hash = utils.sha1hash(self.parentGuid)
        return str(Path('Metadata') / 'Albums' / guid_hash[0] / f'{guid_hash[1:]}.bundle')

    def sonicAdventure(
        self: TTrack,
        to: TTrack,
        **kwargs: Any,
    ) -> list[TTrack]:
        """Returns a sonic adventure from the current track to the specified track.

        Parameters:
            to (:class:`~plexapi.audio.Track`): The target track for the sonic adventure.
            **kwargs: Additional options passed into :func:`~plexapi.library.MusicSection.sonicAdventure`.

        Returns:
            List[:class:`~plexapi.audio.Track`]: list of tracks in the sonic adventure.
        """
        return self.section().sonicAdventure(self, to, **kwargs)


@utils.registerPlexObject
class TrackSession(PlexSession, Track):
    """ Represents a single Track session
        loaded from :func:`~plexapi.server.PlexServer.sessions`.
    """
    _SESSIONTYPE = True

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        Track._loadData(self, data)
        PlexSession._loadData(self, data)


@utils.registerPlexObject
class TrackHistory(PlexHistory, Track):
    """ Represents a single Track history entry
        loaded from :func:`~plexapi.server.PlexServer.history`.
    """
    _HISTORYTYPE = True

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        Track._loadData(self, data)
        PlexHistory._loadData(self, data)
