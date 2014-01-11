# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import urllib2
from xbmcswift2 import xbmc
from xbmcswift2 import Plugin
from xbmcswift2 import xbmcgui
from ChineseKeyboard import Keyboard
from collections_backport import OrderedDict

plugin = Plugin()
dialog = xbmcgui.Dialog()
filters = plugin.get_storage('ftcache', TTL=1440)

@plugin.route('/')
def showcatalog():
    """
    show catalog list
    """
    result = _http('http://www.youku.com/v/')
    catastr = re.search(r'yk-filter-panel">(.*?)yk-filter-handle',
                        result, re.S)
    catalogs = re.findall(r'href="(.*?)".*?>(.*?)</a>', catastr.group(1))
    menus = [{
        'label': catalog[-1].decode('utf-8'),
        'path': plugin.url_for('showmovie',
                            url='http://www.youku.com{0}'.format(catalog[0])),
    } for catalog in catalogs]
    menus.insert(0, {'label': '【搜索视频】选择', 'path': plugin.url_for(
        'searchvideo', url='http://www.soku.com/search_video/q_')})
    return menus

@plugin.route('/searchvideo/<url>')
def searchvideo(url):
    """
    search video
    """
    source = [('http://v.youku.com', 'youku'),
              ('http://tv.sohu.com', 'sohu'),
              ('http://www.iqiyi.com', 'iqiyi'),
              ('http://www.letv.com', 'letv'),
              ('http://v.pps.tv', 'pps'),
              ('http://www.tudou.com', 'tudou')]
    kb = Keyboard('',u'请输入搜索关键字')
    xbmc.sleep(1500)
    kb.doModal()
    if kb.isConfirmed():
        searchStr = kb.getText()
        url = url + urllib2.quote(searchStr)
    result = _http(url)
    movstr = re.findall(r'<div class="item">(.*?)<!--item end-->', result, re.S)
    vitempat = re.compile(
        r'{0}{1}'.format('p_link">.*?title="(.*?)".*?p_thumb.*?src="(.*?)"',
                         '.*?status="(.*?)"'), re.S)
    menus = []
    site = None
    for movitem in movstr:
        if 'p_ispaid' in movitem or 'nosource' in movitem: continue
        psrc = re.compile(r'pgm-source(.*?)</div>', re.S).search(movitem)
        if not psrc: continue
        for k in source:
            if k[0] in psrc.group(1):
                site = k
                break
        if not site: continue
        vitem = vitempat.search(movitem)

        if 'class="movie"' in movitem:
            eps = re.search(r'(%s.*?html)' % site[0], movitem, re.S).group(1)
            menus.append({
                'label': '%s【%s】(%s)' % (
                    vitem.group(1), vitem.group(3), site[1]),
                'path': plugin.url_for('playsearch', url=eps, source=site[1]),
                'thumbnail': vitem.group(2),})

        if 'class="tv"' in movitem or 'class="zy"' in movitem:
            if 'class="tv"' in movitem:
                epss = re.findall(
                    r'(%s.*?html).*?>([\w ."]+?)</a>' % site[0], movitem, re.S)
            else:
                epss = re.findall(r'"date">([\d-]+)<.*?({0}.*?html){1}'.format(
                    site[0],'.*?>([\w ."]+?)</a>(?su)'),movitem.decode('utf-8'))
                epss = [(i[1], '%s-%s' % (i[0], i[2])) for i in epss]

            epss = reversed([(k, v) for k,v in OrderedDict(reversed(epss)).
                             iteritems() if u'查看全部' not in v])
            epss = [(v[0], site[1], v[1]) for v in epss]
            menus.append({
                'label': '%s【%s】(%s)' % (
                    vitem.group(1), vitem.group(3), site[1]),
                'path': plugin.url_for('showsearch', url=str(epss)),
                'thumbnail': vitem.group(2),})
    return menus

@plugin.route('/showsearch/<url>')
def showsearch(url):
    """
    url: 0 is url, 1 is play site, 2 is title
    """
    items = eval(url)
    if len(items)>100:
        items = sorted(list(set(items)), key=lambda item: int(item[2]))
    menus = [{'label': item[2],
              'path': plugin.url_for('playsearch', url=item[0], source=item[1]),
          } for item in items]
    return menus

@plugin.route('/movies/<url>')
def showmovie(url):
    """
    show movie list
    """
    #filter key, e.g. 'http://www.youku.com/v_showlist/c90'
    urlsps = re.findall(r'(.*?/[a-z]_*\d+)', url)
    key = urlsps[0]
    #filter movie by filters
    if 'change' in url:
        url = key
        for k, v in filters[key].iteritems():
            if '筛选' in k: continue
            fts = [m[1] for m in v]
            selitem = dialog.select(k, fts)
            if selitem is not -1:
                url = '{0}{1}'.format(url,v[selitem][0])
        url='{0}.html'.format(url)
        print '*'*80, url

    result = _http(url)

    #get catalog filter list, filter will be cache
    #filters item example:
    #   key:'http://www.youku.com/v_olist/c_97'
    #   value: '{'地区':('_a_大陆', '大陆', ...)}
    if key not in filters:
        filterstr = re.search(r'yk-filter-panel">(.*?)yk-filter-handle',
                            result, re.S)
        filtertypes = re.findall(r'<label>(.*?)<.*?<ul>(.*?)</ul>',
                                 filterstr.group(1), re.S)
        types = OrderedDict()
        for filtertype in filtertypes[1:]:
            typeitems = re.findall(r'(_*[a-z]+_*[^_]+?).html">(.*?)</a>',
                                       filtertype[1], re.S)
            typeitems.insert(0, ('', '全部'))
            types[filtertype[0]] = typeitems
        yksorts = re.findall(r'yk-sort-item(.*?)/ul>', result, re.S)
        for seq, yksort in enumerate(yksorts):
            if 'v_olist' in key:
                sorts = re.findall(r'(_s_\d+)(_d_\d+).*?>(.*?)</a>', yksort)
                types['排序{0}'.format(seq)] = [(s[seq], s[2]) for s in sorts]
            else:
                sorts = re.findall(r'(d\d+)(s\d+).*?>(.*?)</a>', yksort)
                types['排序{0}'.format(seq)] = [(s[not seq], s[2]) for s in sorts]
        filters[key] = types

    #get movie list
    mstr = r'{0}{1}{2}'.format('[vp]-thumb">\s+<img src="(.*?)" alt="(.*?)">',
                               '.*?"[pv]-thumb-tag[lr]b"><.*?">([^<]+?)',
                               '<.*?"[pv]-link">\s+<a href="(.*?)"')
    movies = re.findall(mstr, result, re.S)
    #deduplication movie item
    #movies = [(k,v) for k,v in OrderedDict(movies).iteritems()]

    #add pre/next item
    pagestr = re.search(r'class="yk-pages">(.*?)</ul>',
                        result, re.S)
    if pagestr:
        pre = re.findall(r'class="prev" title="(.*?)">\s*<a href="(.*?)"',
                         pagestr.group(1))
        if pre: movies.append(('', pre[0][0], '',
                               'http://www.youku.com{0}'.format(pre[0][1])))
        nex = re.findall(r'class="next" title="(.*?)">\s*<a href="(.*?)"',
                         pagestr.group(1))
        if nex: movies.append(('', nex[0][0], '',
                               'http://www.youku.com{0}'.format(nex[0][1])))
        cpg = re.findall(r'class="current">.*?>(\d+)<', pagestr.group(1))
        tpg = re.findall(r'class="pass".*?>(\d+)<', pagestr.group(1), re.S)

        #add fliter item
        pagetitle = '【第{0}页/共{1}页】【[COLOR FFFF0000]过滤条件选择)[/COLOR]】'
        movies.insert(0, ('', pagetitle.format(cpg[0], tpg[0] if tpg else '1'),
                          '', '{0}change'.format(url)))
    maptuple = (('olist', 'showmovie'), ('showlist', 'showmovie'),
                ('show_page', 'showepisode'), ('v_show/', 'playmovie'))
    menus = []
    #0 is thunmnailimg, 1 is title, 2 is status, 3 is url
    for seq, m in enumerate(movies):
        routeaddr = filter(lambda x: x[0] in m[3], maptuple)
        menus.append({
            'label': '{0}. {1}【{2}】'.format(seq, m[1], m[2]).decode(
                'utf-8') if m[0] else m[1].decode('utf-8'),
            'path': plugin.url_for(routeaddr[0][1] ,url=m[3]),
            'thumbnail': m[0],
        })
    return menus

@plugin.route('/episodes/<url>')
def showepisode(url):
    """
    show episodes list
    """
    result = _http(url)
    episodestr = re.search(r'id="episode_wrap">(.*?)<div id="point_wrap',
                           result, re.S)
    patt = re.compile(r'(http://v.youku.com/v_show/.*?.html)".*?>([^<]+?)</a')
    episodes = patt.findall(episodestr.group(1))

    #some catalog not episode, e.g. most movie
    if not episodes:
        playurl = re.search(r'class="btnplay" href="(.*?)"', result)
        if not playurl:
            playurl = re.search(r'btnplayposi".*?"(http:.*?)"', result)
        if not playurl:
            playurl = re.search(r'btnplaytrailer.*?(http:.*?)"', result)
        playmovie(playurl.group(1))
    else:
        elists = re.findall(r'<li data="(reload_\d+)" >', result)
        epiurlpart = url.replace('page', 'episode')
        for elist in elists:
            epiurl = epiurlpart + '?divid={0}'.format(elist)
            result = _http(epiurl)
            epimore = patt.findall(result)
            episodes.extend(epimore)

        menus = [{
            'label': episode[1].decode('utf-8'),
            'path': plugin.url_for('playmovie', url=episode[0]),
            } for episode in episodes]
        return menus

@plugin.route('/play/<url>')
@plugin.route('/play/<url>/<source>', name='playsearch')
def playmovie(url, source='youku'):
    """
    play movie
    """
    playutil = PlayUtil(url, source)
    movurl = getattr(playutil, source, playutil.notsup)()
    if 'not support' in movurl:
        xbmcgui.Dialog().ok(
            '提示框', '不支持的播放源,目前支持youku/sohu/iqiyi/pps/letv/tudou')
        return
    listitem=xbmcgui.ListItem()
    listitem.setInfo(type="Video", infoLabels={'Title': 'c'})
    xbmc.Player().play(movurl, listitem)

def _http(url):
    """
    open url
    """
    req = urllib2.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) {0}{1}'.
                   format('AppleWebKit/537.36 (KHTML, like Gecko) ',
                          'Chrome/28.0.1500.71 Safari/537.36'))
    conn = urllib2.urlopen(req, timeout=30)
    content = conn.read()
    conn.close()
    return content


class PlayUtil(object):
    def __init__(self, url, source='youku'):
        self.url = url
        self.source = source
        dialog = xbmcgui.Dialog()

    def notsup(self):
        print '*'*20, source
        return 'not support'

    def youku(self):
        stypes = OrderedDict((('原画', 'hd3'), ('超清', 'hd2'),
                              ('高清', 'mp4'), ('标清', 'flv')))
        #get movie metadata (json format)
        vid = self.url[-18:-5]
        moviesurl="http://v.youku.com/player/getPlayList/VideoIDS/{0}".format(
            vid)
        result = _http(moviesurl)
        movinfo = json.loads(result.replace('\r\n',''))
        movdat = movinfo['data'][0]
        streamfids = movdat['streamfileids']
        stype = 'flv'

        # user select streamtype
        if len(streamfids) > 1:
            selstypes = [k for k,v in stypes.iteritems() if v in streamfids]
            selitem = dialog.select('清晰度', selstypes)
            if selitem is not -1:
                stype = stypes[selstypes[selitem]]

        #stream file format type is mp4 or flv
        ftype = 'mp4' if stype in 'mp4' else 'flv'
        fileid = self._getfileid(streamfids[stype], int(movdat['seed']))
        movsegs = movdat['segs'][stype]
        rooturl = 'http://f.youku.com/player/getFlvPath/sid/00_00/st'
        segurls = []
        for movseg in movsegs:
            #youku split stream file to seg
            segid = '{0}{1:02X}{2}'.format(fileid[0:8],
                                           int(movseg['no']) ,fileid[10:])
            kstr = movseg['k']
            segurl = '{0}/{1}/fileid/{2}?K={3}'.format(
                rooturl, ftype, segid, kstr)
            segurls.append(segurl)
        movurl = 'stack://{0}'.format(' , '.join(segurls))
        return movurl

    def sohu(self):
        html = _http(self.url)
        vid = re.search(r'\Wvid\s*[\:=]\s*[\'"]?(\d+)[\'"]?', html).group(1)
        data = json.loads(_http(
            'http://hot.vrs.sohu.com/vrs_flash.action?vid=%s' % vid))
        qtyps = [('超清', 'superVid'), ('高清', 'highVid'), ('流畅', 'norVid')]
        sel = dialog.select('清晰度', [q[0] for q in qtyps])
        if sel is not -1:
            qtyp = data['data'][qtyps[sel][1]]
            if qtyp and qtyp != vid:
                data = json.loads(_http(
                    'http://hot.vrs.sohu.com/vrs_flash.action?vid=%s' % qtyp))
        host = data['allot']
        prot = data['prot']
        urls = []
        data = data['data']
        title = data['tvName']
        size = sum(data['clipsBytes'])
        for file, new in zip(data['clipsURL'], data['su']):
            urls.append(self.real_url(host, prot, file, new))
        assert data['clipsURL'][0].endswith('.mp4')
        movurl = 'stack://{0}'.format(' , '.join(urls))
        return movurl

    def iqiyi(self):
        html = _http(self.url)
        videoId = re.search(r'data-player-videoid="([^"]+)"', html).group(1)

        info_url = 'http://cache.video.qiyi.com/v/%s' % videoId
        info_xml = _http(info_url)

        from xml.dom.minidom import parseString
        doc = parseString(info_xml)
        title = doc.getElementsByTagName('title')[0].firstChild.nodeValue
        size = int(doc.getElementsByTagName('totalBytes')[0].
                   firstChild.nodeValue)
        urls = [n.firstChild.nodeValue
                for n in doc.getElementsByTagName('file')]
        assert urls[0].endswith('.f4v'), urls[0]

        for i in range(len(urls)):
            temp_url = "http://data.video.qiyi.com/%s" % urls[i].split(
                "/")[-1].split(".")[0] + ".ts"
            try:
                req = urllib2.Request(temp_url)
                urllib2.urlopen(req, timeout=30)
            except urllib2.HTTPError as e:
                key = re.search(r'key=(.*)', e.geturl()).group(1)
            assert key
            urls[i] += "?key=%s" % key
        movurl = 'stack://{0}'.format(' , '.join(urls))
        return movurl

    def pps(self):
        vid = self.url[:-5].split('_')[1]
        html = _http(
            'http://dp.ppstream.com/get_play_url_cdn.php?sid={0}{1}'.format(
                vid,'&flash_type=1'))
        movstr = re.compile(r'(http://.*?)\?hd=').search(html).group(1)
        return movstr

    def tudou(self):
        html = _http(self.url)
        vcode = re.search(r'vcode\s*[:=]\s*\'([^\']+)\'', html).group(1)
        self.url = 'http://v.youku.com/v_show/id_{0}.html'.format(vcode)
        self.youku()


    def letv(self):
        vid = self.url.split('/')[-1][:-5]
        infoxml = _http('http://www.letv.com/v_xml/{0}.xml'.format(vid))
        dispatch = re.search(
            r'dispatch":({.*?}),"dispatchbak"', infoxml, re.S).group(1)
        streams = eval(dispatch)
        sinfo = streams['1300']
        qtyps = [('1080P', '1080p'), ('超清', '720p'), ('高清', '1300'),
                 ('标清', '1000'), ('流畅', '350')]
        sel = dialog.select('清晰度', [q[0] for q in qtyps])
        if sel is not -1:
            sinfo = streams[qtyps[sel][1]]
        resp = urllib2.urlopen('http://g3.letv.cn/{0}'.format(
            sinfo[2].replace('\\','')), timeout=30)
        movurl = resp.geturl()
        return movurl

    def _getfileid(self, streamid, seed):
        """
        get dynamic stream file id
        Arguments:
        - `streamid`: e.g. '48*60*21*...*13*'
        - `seed`: mix str seed
        """
        source = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'\
                 '/\\:._-1234567890'
        index = 0
        mixed = []
        for i in range(len(source)):
            seed = (seed * 211 + 30031) % 65536
            index =  seed * len(source) / 65536
            mixed.append(source[index])
            source = source.replace(source[index],"")
        mixstr = ''.join(mixed)
        attr = streamid[:-1].split('*')
        res = ""
        for item in attr:
            res +=  mixstr[int(item)]
        return res

    def real_url(self, host, prot, file, new):
        url = 'http://%s/?prot=%s&file=%s&new=%s' % (host, prot, file, new)
        start, _, host, key = _http(url).split('|')[:4]
        return '%s%s?key=%s' % (start[:-1], new, key)

if __name__ == '__main__':
    #filters.clear()
    plugin.run()
