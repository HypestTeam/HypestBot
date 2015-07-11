import requests
import re, json

game_to_filename = {
    '3ds': 'ssb3ds.json',
    'wiiu': 'ssbwiiu.json',
    'melee': 'ssbm.json',
    'brawl': 'ssbb.json',
    'projectm': 'projectm.json',
    'ssf2': 'ssf2.json',
    '64': 'ssb64.json',
    16869: 'ssb3ds.json',
    20988: 'ssbwiiu.json',
    394: 'ssbm.json',
    393: 'ssbb.json',
    392: 'ssb64.json',
    597: 'projectm.json',
    1106: 'ssf2.json'
}

"""An exception thrown when challonge reports an error"""
class ChallongeAPIError(Exception):
    pass

"""An exception thrown when the seasonal ranking procedure fails somehow"""
class RankingError(Exception):
    pass

"""An object that represents a player"""
class Player(object):
    def __init__(self, id):
        # challonge participant ID
        self.id = id
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.final_rank = None
        self.name = ''

"""An object that represents a match on challonge"""
class Match(object):
    def __init__(self, match_json):
        self.player1_id = match_json['player1_id']
        self.player2_id = match_json['player2_id']
        self.winner_id  = match_json['winner_id']

"""An object that represents the challonge API"""
class Challonge(object):
    API_BASE_URL = 'https://api.challonge.com/v1'

    def __init__(self, api_key):
        self.api_key = api_key

    @staticmethod
    def prepare_url(url):
        # https://subdomain.challonge.com/id -> subdomain.challonge.com/id -> subdomain.id -> [subdomain, id]
        fragments = re.sub(r'https?:\/\/', '', url).replace('challonge.com/', '').split('.')

        if len(fragments) == 2:
            return '{0[0]}-{0[1]}'.format(fragments)
        return url

    @staticmethod
    def get_display_name(participant):
        """Returns the challonge username if applicable, otherwise returns the display name"""
        challonge_username = participant.get('challonge_username')
        return challonge_username if challonge_username else participant.get('display_name')

    def show_tournament(self, url):
        """Returns a tournament with matches and participants"""
        params = {
            'api_key': self.api_key,
            'include_matches': '1',
            'include_participants': '1'
        }

        new_url = Challonge.prepare_url(url)
        r = requests.get('{}/tournaments/{}.json'.format(Challonge.API_BASE_URL, new_url), params=params)
        if r.status_code != 200:
            raise ChallongeAPIError("unable to retrieve challonge tournament (url: {})".format(url))

        return r.json()['tournament']


def get_player_standings(tournament):
    """Returns a list of Player objects with overall tournament statistics and placings"""
    list_of_matches = tournament['matches']
    cache = {}
    for obj in list_of_matches:
        match = Match(obj['match'])
        player_one = cache.setdefault(match.player1_id, Player(match.player1_id))
        player_two = cache.setdefault(match.player2_id, Player(match.player2_id))

        if match.winner_id == match.player1_id:
            player_one.wins += 1
            player_two.losses += 1
        elif match.winner_id == match.player2_id:
            player_one.losses += 1
            player_two.wins += 1
        else:
            player_one.ties += 1
            player_two.ties += 1

    # retrieve the names
    list_of_participants = tournament['participants']
    for obj in list_of_participants:
        participant = obj['participant']
        player = cache.get(participant.id, None)
        if player is not None:
            player.name = Challonge.get_display_name(participant)
            player.final_rank = participant.get('final_rank', 0)

    return cache.values()

def get_ranking_filename(game_id):
    filename = game_to_filename.get(game_id, None)
    if filename is None:
        raise RankingError('Unknown game id found: {}'.format(game_id))
    return filename

def get_rankings(filename):
    """Returns the data with the seasonal ranking

        The seasonal ranking file is a dictionary with
        a display_name:ranking mapping"""
    with open(filename, 'r') as f:
        return json.load(f)

def update_rankings(url, api_key):
    """Updates the seasonal rankings for the current game
       The current score values are as follows:
       Round Win - 3 points
       Round Loss - 0 points
       Round Tie - 1 point
       This might be changed in the future"""

    challonge = Challonge(api_key)
    tournament = challonge.show_tournament(url)
    if tournament['state'] != 'complete':
        raise RankingError('The tournament is incomplete')

    game_id = tournament['game_id']
    filename = get_ranking_filename(game_id)
    current_ranking = get_rankings(filename)
    players = get_player_standings(tournament)

    for player in players:
        ranking = current_ranking.setdefault(player.display_name, 0)
        ranking += 3 * player.wins
        ranking += 1 * player.ties
        current_ranking[player.display_name] = ranking

    with open(filename, 'w') as f:
        json.dump(current_ranking, f, ensure_ascii=True, indent=4)
