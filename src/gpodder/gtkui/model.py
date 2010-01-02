# -*- coding: utf-8 -*-
#
# gPodder - A media aggregator and podcast client
# Copyright (c) 2005-2010 Thomas Perl and the gPodder Team
#
# gPodder is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# gPodder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


#
#  gpodder.gtkui.model - GUI model classes for gPodder (2009-08-13)
#  Based on code from libpodcasts.py (thp, 2005-10-29)
#

import gpodder

_ = gpodder.gettext

from gpodder import util

from gpodder.gtkui import draw

import gtk
import xml.sax.saxutils

class EpisodeListModel(gtk.ListStore):
    C_URL, C_TITLE, C_FILESIZE_TEXT, C_EPISODE, C_STATUS_ICON, \
            C_PUBLISHED_TEXT, C_DESCRIPTION, C_TOOLTIP, \
            C_VIEW_SHOW_UNDELETED, C_VIEW_SHOW_DOWNLOADED, \
            C_VIEW_SHOW_UNPLAYED = range(11)

    SEARCH_COLUMNS = (C_TITLE, C_DESCRIPTION)

    VIEW_ALL, VIEW_UNDELETED, VIEW_DOWNLOADED, VIEW_UNPLAYED = range(4)

    def __init__(self):
        gtk.ListStore.__init__(self, str, str, str, object, \
                gtk.gdk.Pixbuf, str, str, str, bool, bool, bool)

        # Filter to allow hiding some episodes
        self._filter = self.filter_new()
        self._view_mode = self.VIEW_ALL
        self._search_term = None
        self._filter.set_visible_func(self._filter_visible_func)

        # "ICON" is used to mark icon names in source files
        ICON = lambda x: x

        self._icon_cache = {}
        self.ICON_AUDIO_FILE = ICON('audio-x-generic')
        self.ICON_VIDEO_FILE = ICON('video-x-generic')
        self.ICON_GENERIC_FILE = ICON('text-x-generic')
        self.ICON_DOWNLOADING = gtk.STOCK_GO_DOWN
        self.ICON_DELETED = gtk.STOCK_DELETE
        self.ICON_NEW = gtk.STOCK_ABOUT
        self.ICON_UNPLAYED = ICON('emblem-new')
        self.ICON_LOCKED = ICON('emblem-readonly')
        self.ICON_MISSING = ICON('emblem-unreadable')


    def _format_filesize(self, episode):
        if episode.length > 0:
            return util.format_filesize(episode.length, 1)
        else:
            return None


    def _filter_visible_func(self, model, iter):
        # If searching is active, set visibility based on search text
        if self._search_term is not None:
            key = self._search_term.lower()
            return any((key in (model.get_value(iter, column) or '').lower()) for column in self.SEARCH_COLUMNS)

        if self._view_mode == self.VIEW_ALL:
            return True
        elif self._view_mode == self.VIEW_UNDELETED:
            return model.get_value(iter, self.C_VIEW_SHOW_UNDELETED)
        elif self._view_mode == self.VIEW_DOWNLOADED:
            return model.get_value(iter, self.C_VIEW_SHOW_DOWNLOADED)
        elif self._view_mode == self.VIEW_UNPLAYED:
            return model.get_value(iter, self.C_VIEW_SHOW_UNPLAYED)

        return True

    def get_filtered_model(self):
        """Returns a filtered version of this episode model

        The filtered version should be displayed in the UI,
        as this model can have some filters set that should
        be reflected in the UI.
        """
        return self._filter

    def set_view_mode(self, new_mode):
        """Sets a new view mode for this model

        After setting the view mode, the filtered model
        might be updated to reflect the new mode."""
        if self._view_mode != new_mode:
            self._view_mode = new_mode
            self._filter.refilter()

    def get_view_mode(self):
        """Returns the currently-set view mode"""
        return self._view_mode

    def set_search_term(self, new_term):
        if self._search_term != new_term:
            self._search_term = new_term
            self._filter.refilter()

    def get_search_term(self):
        return self._search_term

    def _format_description(self, episode, include_description=False, is_downloading=None):
        if include_description:
            return '%s\n<small>%s</small>' % (xml.sax.saxutils.escape(episode.title),
                    xml.sax.saxutils.escape(episode.one_line_description()))
        else:
            return xml.sax.saxutils.escape(episode.title)

    def add_from_channel(self, channel, downloading=None, \
            include_description=False):
        """
        Add episode from the given channel to this model.
        Downloading should be a callback.
        include_description should be a boolean value (True if description
        is to be added to the episode row, or False if not)
        """
        def insert_and_update(episode):
            description_stripped = util.remove_html_tags(episode.description)

            iter = self.append()
            self.set(iter, \
                    self.C_URL, episode.url, \
                    self.C_TITLE, episode.title, \
                    self.C_FILESIZE_TEXT, self._format_filesize(episode), \
                    self.C_EPISODE, episode, \
                    self.C_PUBLISHED_TEXT, episode.cute_pubdate(), \
                    self.C_TOOLTIP, description_stripped)

            self.update_by_iter(iter, downloading, include_description)

        for episode in channel.get_all_episodes():
            util.idle_add(insert_and_update, episode)

    def update_all(self, downloading=None, include_description=False):
        for row in self:
            self.update_by_iter(row.iter, downloading, include_description)

    def update_by_urls(self, urls, downloading=None, include_description=False):
        for row in self:
            if row[self.C_URL] in urls:
                self.update_by_iter(row.iter, downloading, include_description)

    def update_by_filter_iter(self, iter, downloading=None, \
            include_description=False):
        # Convenience function for use by "outside" methods that use iters
        # from the filtered episode list model (i.e. all UI things normally)
        self.update_by_iter(self._filter.convert_iter_to_child_iter(iter), \
                downloading, include_description)

    def update_by_iter(self, iter, downloading=None, include_description=False):
        episode = self.get_value(iter, self.C_EPISODE)
        episode.reload_from_db()

        if include_description or gpodder.ui.maemo:
            icon_size = 32
        else:
            icon_size = 16

        show_bullet = False
        show_padlock = False
        show_missing = False
        status_icon = None
        tooltip = ''
        view_show_undeleted = True
        view_show_downloaded = False
        view_show_unplayed = False

        if downloading is not None and downloading(episode):
            tooltip = _('Downloading')
            status_icon = self.ICON_DOWNLOADING
            view_show_downloaded = True
            view_show_unplayed = True
        else:
            if episode.state == gpodder.STATE_DELETED:
                tooltip = _('Deleted')
                status_icon = self.ICON_DELETED
                view_show_undeleted = False
            elif episode.state == gpodder.STATE_NORMAL and \
                    not episode.is_played:
                tooltip = _('New episode')
                status_icon = self.ICON_NEW
                view_show_downloaded = True
                view_show_unplayed = True
            elif episode.state == gpodder.STATE_DOWNLOADED:
                tooltip = []
                view_show_downloaded = True
                view_show_unplayed = not episode.is_played
                show_bullet = not episode.is_played
                show_padlock = episode.is_locked
                show_missing = not episode.file_exists()

                file_type = episode.file_type()
                if file_type == 'audio':
                    tooltip.append(_('Downloaded episode'))
                    status_icon = self.ICON_AUDIO_FILE
                elif file_type == 'video':
                    tooltip.append(_('Downloaded video episode'))
                    status_icon = self.ICON_VIDEO_FILE
                else:
                    tooltip.append(_('Downloaded file'))
                    status_icon = self.ICON_GENERIC_FILE

                if show_missing:
                    tooltip.append(_('missing file'))
                else:
                    if show_bullet:
                        tooltip.append(_('never played'))
                    else:
                        tooltip.append(_('played'))
                    if show_padlock:
                        tooltip.append(_('deletion prevented'))

                tooltip = ', '.join(tooltip)

        if status_icon is not None:
            status_icon = self._get_tree_icon(status_icon, show_bullet, \
                    show_padlock, show_missing, icon_size)

        description = self._format_description(episode, include_description, downloading)
        self.set(iter, \
                self.C_STATUS_ICON, status_icon, \
                self.C_VIEW_SHOW_UNDELETED, view_show_undeleted, \
                self.C_VIEW_SHOW_DOWNLOADED, view_show_downloaded, \
                self.C_VIEW_SHOW_UNPLAYED, view_show_unplayed, \
                self.C_DESCRIPTION, description, \
                self.C_TOOLTIP, tooltip)

    def _get_tree_icon(self, icon_name, add_bullet=False, \
            add_padlock=False, add_missing=False, icon_size=32):
        """
        Loads an icon from the current icon theme at the specified
        size, suitable for display in a gtk.TreeView. Additional
        emblems can be added on top of the icon.

        Caching is used to speed up the icon lookup.
        """

        # Add all variables that modify the appearance of the icon, so
        # our cache does not return the same icons for different requests
        cache_id = (icon_name, add_bullet, add_padlock, add_missing, icon_size)

        if cache_id in self._icon_cache:
            return self._icon_cache[cache_id]

        icon_theme = gtk.icon_theme_get_default()

        try:
            icon = icon_theme.load_icon(icon_name, icon_size, 0)
        except:
            icon = icon_theme.load_icon(gtk.STOCK_DIALOG_QUESTION, icon_size, 0)

        if icon and (add_bullet or add_padlock or add_missing):
            # We'll modify the icon, so use .copy()
            if add_missing:
                try:
                    icon = icon.copy()
                    # Desaturate the icon so it looks even more "missing"
                    icon.saturate_and_pixelate(icon, 0.0, False)
                    emblem = icon_theme.load_icon(self.ICON_MISSING, icon_size/2, 0)
                    (width, height) = (emblem.get_width(), emblem.get_height())
                    xpos = icon.get_width() - width
                    ypos = icon.get_height() - height
                    emblem.composite(icon, xpos, ypos, width, height, xpos, ypos, 1, 1, gtk.gdk.INTERP_BILINEAR, 255)
                except:
                    pass
            elif add_bullet:
                try:
                    icon = icon.copy()
                    emblem = icon_theme.load_icon(self.ICON_UNPLAYED, icon_size/2, 0)
                    (width, height) = (emblem.get_width(), emblem.get_height())
                    xpos = icon.get_width() - width
                    ypos = icon.get_height() - height
                    emblem.composite(icon, xpos, ypos, width, height, xpos, ypos, 1, 1, gtk.gdk.INTERP_BILINEAR, 255)
                except:
                    pass
            if add_padlock:
                try:
                    icon = icon.copy()
                    emblem = icon_theme.load_icon(self.ICON_LOCKED, icon_size/2, 0)
                    (width, height) = (emblem.get_width(), emblem.get_height())
                    emblem.composite(icon, 0, 0, width, height, 0, 0, 1, 1, gtk.gdk.INTERP_BILINEAR, 255)
                except:
                    pass

        self._icon_cache[cache_id] = icon
        return icon


class PodcastChannelProxy(object):
    def __init__(self, db, config, channels):
        self._db = db
        self._config = config
        self.channels = channels
        self.title =  _('All episodes')
        self.description = _('from all podcasts')
        self.parse_error = ''
        self.url = ''
        self.id = None
        self._save_dir_size_set = False
        self.save_dir_size = 0L
        self.icon = None

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            log('Unsupported method call (%s)', name, sender=self)

    def get_statistics(self):
        # Get the total statistics for all channels from the database
        return self._db.get_total_count()

    def get_all_episodes(self):
        """Returns a generator that yields every episode"""
        for channel in self.channels:
            for episode in channel.get_all_episodes():
                yield episode

    def request_save_dir_size(self):
        if not self._save_dir_size_set:
            self.update_save_dir_size()
        self._save_dir_size_set = True

    def update_save_dir_size(self):
        self.save_dir_size = util.calculate_size(self._config.download_dir)


class PodcastListModel(gtk.ListStore):
    C_URL, C_TITLE, C_DESCRIPTION, C_PILL, C_CHANNEL, \
            C_COVER, C_ERROR, C_PILL_VISIBLE, \
            C_VIEW_SHOW_UNDELETED, C_VIEW_SHOW_DOWNLOADED, \
            C_VIEW_SHOW_UNPLAYED, C_HAS_EPISODES, C_SEPARATOR = range(13)

    SEARCH_COLUMNS = (C_TITLE, C_DESCRIPTION)

    @classmethod
    def row_separator_func(cls, model, iter):
        return model.get_value(iter, cls.C_SEPARATOR)

    def __init__(self, max_image_side, cover_downloader):
        gtk.ListStore.__init__(self, str, str, str, gtk.gdk.Pixbuf, \
                object, gtk.gdk.Pixbuf, str, bool, bool, bool, bool, bool, bool)

        # Filter to allow hiding some episodes
        self._filter = self.filter_new()
        self._view_mode = -1
        self._search_term = None
        self._filter.set_visible_func(self._filter_visible_func)

        self._cover_cache = {}
        if gpodder.ui.fremantle:
            self._max_image_side = 64
        else:
            self._max_image_side = max_image_side
        self._cover_downloader = cover_downloader

    def _filter_visible_func(self, model, iter):
        # If searching is active, set visibility based on search text
        if self._search_term is not None:
            key = self._search_term.lower()
            return any((key in model.get_value(iter, column).lower()) for column in self.SEARCH_COLUMNS)

        if model.get_value(iter, self.C_SEPARATOR):
            return True
        if self._view_mode == EpisodeListModel.VIEW_ALL:
            return model.get_value(iter, self.C_HAS_EPISODES)
        elif self._view_mode == EpisodeListModel.VIEW_UNDELETED:
            return model.get_value(iter, self.C_VIEW_SHOW_UNDELETED)
        elif self._view_mode == EpisodeListModel.VIEW_DOWNLOADED:
            return model.get_value(iter, self.C_VIEW_SHOW_DOWNLOADED)
        elif self._view_mode == EpisodeListModel.VIEW_UNPLAYED:
            return model.get_value(iter, self.C_VIEW_SHOW_UNPLAYED)

        return True

    def get_filtered_model(self):
        """Returns a filtered version of this episode model

        The filtered version should be displayed in the UI,
        as this model can have some filters set that should
        be reflected in the UI.
        """
        return self._filter

    def set_view_mode(self, new_mode):
        """Sets a new view mode for this model

        After setting the view mode, the filtered model
        might be updated to reflect the new mode."""
        if self._view_mode != new_mode:
            self._view_mode = new_mode
            self._filter.refilter()

    def get_view_mode(self):
        """Returns the currently-set view mode"""
        return self._view_mode

    def set_search_term(self, new_term):
        if self._search_term != new_term:
            self._search_term = new_term
            self._filter.refilter()

    def get_search_term(self):
        return self._search_term

    def enable_separators(self, channeltree):
        channeltree.set_row_separator_func(self._show_row_separator)

    def _show_row_separator(self, model, iter):
        return model.get_value(iter, self.C_SEPARATOR)

    def _resize_pixbuf_keep_ratio(self, url, pixbuf):
        """
        Resizes a GTK Pixbuf but keeps its aspect ratio.
        Returns None if the pixbuf does not need to be
        resized or the newly resized pixbuf if it does.
        """
        changed = False
        result = None

        if url in self._cover_cache:
            return self._cover_cache[url]

        # Resize if too wide
        if pixbuf.get_width() > self._max_image_side:
            f = float(self._max_image_side)/pixbuf.get_width()
            (width, height) = (int(pixbuf.get_width()*f), int(pixbuf.get_height()*f))
            pixbuf = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
            changed = True

        # Resize if too high
        if pixbuf.get_height() > self._max_image_side:
            f = float(self._max_image_side)/pixbuf.get_height()
            (width, height) = (int(pixbuf.get_width()*f), int(pixbuf.get_height()*f))
            pixbuf = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
            changed = True

        if changed:
            self._cover_cache[url] = pixbuf
            result = pixbuf

        return result

    def _resize_pixbuf(self, url, pixbuf):
        if pixbuf is None:
            return None

        return self._resize_pixbuf_keep_ratio(url, pixbuf) or pixbuf

    def _get_cover_image(self, channel):
        if self._cover_downloader is None:
            return None

        pixbuf = self._cover_downloader.get_cover(channel, avoid_downloading=True)
        return self._resize_pixbuf(channel.url, pixbuf)

    def _get_pill_image(self, channel, count_downloaded, count_unplayed):
        if count_unplayed > 0 or count_downloaded > 0:
            return draw.draw_pill_pixbuf(str(count_unplayed), str(count_downloaded))
        else:
            return None

    def _format_description(self, channel, total, deleted, \
            new, downloaded, unplayed):
        title_markup = xml.sax.saxutils.escape(channel.title)
        description_markup = xml.sax.saxutils.escape(util.get_first_line(channel.description) or ' ')
        d = []
        if new:
            d.append('<span weight="bold">')
        d.append(title_markup)
        if new:
            d.append('</span>')
        return ''.join(d+['\n', '<small>', description_markup, '</small>'])

    def _format_error(self, channel):
        if channel.parse_error:
            return str(channel.parse_error)
        else:
            return None

    def set_channels(self, db, config, channels):
        # Clear the model and update the list of podcasts
        self.clear()

        if config.podcast_list_view_all:
            all_episodes = PodcastChannelProxy(db, config, channels)
            iter = self.append()
            self.set(iter, \
                    self.C_URL, all_episodes.url, \
                    self.C_CHANNEL, all_episodes, \
                    self.C_COVER, all_episodes.icon, \
                    self.C_SEPARATOR, False)
            self.update_by_iter(iter)

            iter = self.append()
            self.set(iter, self.C_SEPARATOR, True)

        for channel in channels:
            iter = self.append()
            self.set(iter, \
                    self.C_URL, channel.url, \
                    self.C_CHANNEL, channel, \
                    self.C_COVER, self._get_cover_image(channel), \
                    self.C_SEPARATOR, False)
            self.update_by_iter(iter)

    def get_filter_path_from_url(self, url):
        # Return the path of the filtered model for a given URL
        child_path = self.get_path_from_url(url)
        if child_path is None:
            return None
        else:
            return self._filter.convert_child_path_to_path(child_path)

    def get_path_from_url(self, url):
        # Return the tree model path for a given URL
        if url is None:
            return None

        for row in self:
            if row[self.C_URL] == url:
                    return row.path
        return None

    def update_by_urls(self, urls):
        # Given a list of URLs, update each matching row
        for row in self:
            if row[self.C_URL] in urls:
                self.update_by_iter(row.iter)

    def update_by_filter_iter(self, iter):
        self.update_by_iter(self._filter.convert_iter_to_child_iter(iter))

    def update_all(self):
        for row in self:
            self.update_by_iter(row.iter)

    def update_by_iter(self, iter):
        # Given a GtkTreeIter, update volatile information
        channel = self.get_value(iter, self.C_CHANNEL)
        if channel is None:
            return
        total, deleted, new, downloaded, unplayed = channel.get_statistics()
        description = self._format_description(channel, total, deleted, new, \
                downloaded, unplayed)

        pill_image = self._get_pill_image(channel, downloaded, unplayed)
        self.set(iter, \
                self.C_TITLE, channel.title, \
                self.C_DESCRIPTION, description, \
                self.C_ERROR, self._format_error(channel), \
                self.C_PILL, pill_image, \
                self.C_PILL_VISIBLE, pill_image != None, \
                self.C_VIEW_SHOW_UNDELETED, total - deleted > 0, \
                self.C_VIEW_SHOW_DOWNLOADED, downloaded + new > 0, \
                self.C_VIEW_SHOW_UNPLAYED, unplayed + new > 0, \
                self.C_HAS_EPISODES, total > 0)

    def add_cover_by_url(self, url, pixbuf):
        # Resize and add the new cover image
        pixbuf = self._resize_pixbuf(url, pixbuf)
        for row in self:
            if row[self.C_URL] == url:
                row[self.C_COVER] = pixbuf
                break

    def delete_cover_by_url(self, url):
        # Remove the cover from the model
        for row in self:
            if row[self.C_URL] == url:
                row[self.C_COVER] = None
                break

        # Remove the cover from the cache
        if url in self._cover_cache:
            del self._cover_cache[url]

